from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from transaction_db import get_db
from transaction_engine.merchant import normalize_merchant
from transaction_engine.money import rupees_to_paise
from ingestion import create_batch
from models import ImportBatch, ImportRow, LearnedCategoryRule, Transaction
from parsers.csv_importer import CsvFormatError, ParsedCsvTransaction, parse_csv_bytes
from parsers.pdf_importer import PdfImportError, ScannedPdfError, parse_pdf
from parsers.sms_parser import parse_sms
from schemas import (
    CategoryCorrection, CategoryCorrectionPreview, CategoryCorrectionResult,
    HealthRead, ImportBatchSummary, LearnedRuleRead, RowIssue, SmsImportRequest,
    SmsParseRequest, SmsParseResponse, TransactionPage, TransactionRead,
)

router = APIRouter(prefix="/api")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _summary(batch: ImportBatch, db: Session) -> ImportBatchSummary:
    rows = db.scalars(select(ImportRow).where(ImportRow.batch_id == batch.id).order_by(ImportRow.row_number, ImportRow.id)).all()
    return ImportBatchSummary(
        batch_id=batch.id, source_format=batch.source_format, source_name=batch.source_name,
        total_rows=batch.total_rows, imported_count=batch.imported_count,
        rejected_count=batch.rejected_count, duplicate_count=batch.duplicate_count,
        probable_duplicate_count=batch.probable_duplicate_count,
        review_required_count=batch.review_required_count, ignored_count=batch.ignored_count,
        balance_reconciliation=batch.balance_reconciliation, warnings=batch.warnings or [],
        rows=[RowIssue(
            row_number=row.row_number, status=row.status, message=row.message,
            raw_source_text=row.raw_source_text,
        ) for row in rows],
    )


async def _read_upload(file: UploadFile) -> bytes:
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB import limit.")
    if not content:
        raise HTTPException(status_code=422, detail="Uploaded file is empty.")
    return content


@router.get("/health", response_model=HealthRead)
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "database": "ok"}


@router.post("/transactions/import/csv", response_model=ImportBatchSummary)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await _read_upload(file)
    try:
        records, errors = parse_csv_bytes(content)
    except CsvFormatError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    batch = create_batch(
        db, source_format="csv", source_name=file.filename, records=records,
        errors=errors, total_rows=len(records) + len(errors),
    )
    return _summary(batch, db)


@router.post("/transactions/import/pdf", response_model=ImportBatchSummary)
async def import_pdf(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await _read_upload(file)
    try:
        parsed = parse_pdf(content)
    except (ScannedPdfError, PdfImportError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    batch = create_batch(
        db, source_format="pdf", source_name=file.filename, records=parsed.records,
        errors=parsed.errors, total_rows=parsed.total_rows,
        balance_reconciliation=parsed.balance_reconciliation, warnings=parsed.warnings,
    )
    return _summary(batch, db)


def _sms_response(parsed) -> SmsParseResponse:
    return SmsParseResponse(
        raw_text=parsed.raw_text, transaction_date=parsed.transaction_date,
        description=parsed.description, normalized_merchant=parsed.normalized_merchant,
        amount_paise=rupees_to_paise(parsed.amount) if parsed.amount is not None else None,
        transaction_type=parsed.transaction_type, category=parsed.category.category,
        confidence_score=parsed.category.confidence_score,
        category_explanation=parsed.category.reason, missing_fields=list(parsed.missing_fields),
        needs_review=parsed.needs_review, ignored_reason=parsed.ignored_reason,
        external_reference=parsed.external_reference,
    )


@router.post("/transactions/parse-sms", response_model=SmsParseResponse)
def parse_sms_preview(request: SmsParseRequest, db: Session = Depends(get_db)):
    return _sms_response(parse_sms(request.text, db))


@router.post("/transactions/import/sms", response_model=ImportBatchSummary)
def import_sms(request: SmsImportRequest, db: Session = Depends(get_db)):
    records: list[tuple[int, ParsedCsvTransaction]] = []
    review_rows: list[tuple[int, str, str]] = []
    ignored_rows: list[tuple[int, str, str]] = []
    for row_number, text in enumerate(request.messages, start=1):
        parsed = parse_sms(text, db)
        if parsed.ignored_reason:
            ignored_rows.append((row_number, parsed.ignored_reason, parsed.raw_text))
            continue
        if parsed.missing_fields:
            review_rows.append((row_number, "Missing or unrecognized: " + ", ".join(parsed.missing_fields), parsed.raw_text))
            continue
        records.append((row_number, ParsedCsvTransaction(
            transaction_date=parsed.transaction_date,
            description=parsed.description,
            normalized_merchant=parsed.normalized_merchant,
            amount=parsed.amount,
            transaction_type=parsed.transaction_type,
            currency="INR",
            raw_text=parsed.raw_text,
            external_reference=parsed.external_reference,
        )))
    batch = create_batch(
        db, source_format="sms", source_name="Pasted SMS", records=records,
        errors=[], total_rows=len(request.messages), review_rows=review_rows,
        ignored_rows=ignored_rows,
    )
    return _summary(batch, db)


@router.get("/transactions", response_model=TransactionPage)
def list_transactions(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    include_duplicates: bool = False,
    review_only: bool = False,
    db: Session = Depends(get_db),
):
    statement = select(Transaction)
    if not include_duplicates:
        statement = statement.where(Transaction.duplicate_status != "duplicate")
    if review_only:
        statement = statement.where(or_(
            Transaction.category == "Review Required",
            Transaction.duplicate_status == "probable_duplicate",
        ))
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(statement.order_by(Transaction.transaction_date.desc(), Transaction.id).limit(limit).offset(offset)).all()
    return TransactionPage(total=total, limit=limit, offset=offset, items=rows)


@router.get("/transactions/{transaction_id}", response_model=TransactionRead)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    return transaction


@router.post("/transactions/{transaction_id}/category/preview", response_model=CategoryCorrectionPreview)
def preview_category_correction(transaction_id: str, request: CategoryCorrection, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    merchant = normalize_merchant(transaction.normalized_merchant)
    if not merchant:
        raise HTTPException(status_code=422, detail="This transaction has no merchant identity to learn a reusable rule from.")
    matches = db.scalars(select(Transaction).where(Transaction.normalized_merchant == merchant).order_by(Transaction.transaction_date.desc())).all()
    eligible = [item for item in matches if item.id == transaction.id or not item.user_locked]
    locked_count = sum(1 for item in matches if item.user_locked and item.id != transaction.id)
    return CategoryCorrectionPreview(
        transaction_id=transaction.id, merchant=merchant, proposed_category=request.category,
        eligible_count=len(eligible), locked_count=locked_count,
        sample_transaction_ids=[item.id for item in eligible[:10]],
    )


@router.patch("/transactions/{transaction_id}/category", response_model=CategoryCorrectionResult)
def correct_category(transaction_id: str, request: CategoryCorrection, db: Session = Depends(get_db)):
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    merchant = normalize_merchant(transaction.normalized_merchant)
    if not merchant:
        raise HTTPException(status_code=422, detail="This transaction has no merchant identity to learn a reusable rule from.")

    rule = db.scalar(select(LearnedCategoryRule).where(LearnedCategoryRule.merchant_key == merchant))
    rule_created = rule is None
    if rule is None:
        rule = LearnedCategoryRule(id=str(uuid.uuid4()), merchant_key=merchant, category=request.category)
        db.add(rule)
    else:
        rule.category = request.category

    transaction.category = request.category
    transaction.confidence_score = 1.0
    transaction.category_explanation = f"User correction saved as merchant rule for '{merchant}'."
    transaction.user_locked = True
    updated_ids = [transaction.id]
    locked_skipped = 0
    if request.apply_to_matching:
        matches = db.scalars(select(Transaction).where(
            Transaction.normalized_merchant == merchant,
            Transaction.id != transaction.id,
        )).all()
        for match in matches:
            if match.user_locked:
                locked_skipped += 1
                continue
            match.category = request.category
            match.confidence_score = 1.0
            match.category_explanation = f"Applied saved merchant rule for '{merchant}'."
            updated_ids.append(match.id)
    db.commit()
    db.refresh(rule)
    return CategoryCorrectionResult(
        transaction_id=transaction.id, merchant=merchant, category=request.category,
        rule_id=rule.id, rule_created=rule_created,
        rule_applied_to_existing_count=len(updated_ids) - 1,
        locked_transactions_skipped=locked_skipped,
        updated_transaction_ids=updated_ids,
        message=("Saved rule for future transactions. Existing matching transactions were updated after explicit apply."
                 if request.apply_to_matching else "Saved rule for future transactions; only the selected transaction was changed."),
    )


@router.get("/rules", response_model=list[LearnedRuleRead])
def list_rules(db: Session = Depends(get_db)):
    return db.scalars(select(LearnedCategoryRule).order_by(LearnedCategoryRule.merchant_key)).all()


@router.get("/import-batches/{batch_id}", response_model=ImportBatchSummary)
def get_import_batch(batch_id: str, db: Session = Depends(get_db)):
    batch = db.get(ImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Import batch not found.")
    return _summary(batch, db)
