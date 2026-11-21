from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from transaction_engine.categorizer import categorize
from transaction_engine.descriptions import clean_description
from transaction_engine.fingerprint import duplicate_fingerprint
from transaction_engine.merchant import normalize_merchant
from transaction_engine.money import rupees_to_paise
from models import ImportBatch, ImportRow, Transaction
from parsers.csv_importer import ParsedCsvTransaction, RowError


@dataclass(frozen=True)
class ParsedImportRow:
    row_number: int
    transaction_date: object
    description: str
    normalized_merchant: str | None
    amount: Decimal
    transaction_type: str
    currency: str
    raw_text: str
    external_reference: str | None = None


def _reference_key(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^a-z0-9]", "", value.casefold())
    return normalized or None


def create_batch(
    db: Session,
    *,
    source_format: str,
    source_name: str | None,
    records: list[tuple[int, ParsedCsvTransaction]],
    errors: list[RowError],
    total_rows: int,
    balance_reconciliation: dict | None = None,
    warnings: list[str] | None = None,
    ignored_count: int = 0,
    review_rows: list[tuple[int, str, str]] | None = None,
    ignored_rows: list[tuple[int, str, str]] | None = None,
) -> ImportBatch:
    batch = ImportBatch(
        id=str(uuid.uuid4()), source_format=source_format, source_name=source_name,
        total_rows=total_rows, imported_count=0, rejected_count=len(errors),
        duplicate_count=0, probable_duplicate_count=0,
        review_required_count=0, ignored_count=ignored_count,
        balance_reconciliation=balance_reconciliation, warnings=warnings or [],
    )
    db.add(batch)
    db.flush()

    # Index existing transactions once. Identical amount alone is never considered a duplicate.
    existing = db.scalars(select(Transaction)).all()
    by_ref: dict[tuple, list[Transaction]] = {}
    by_fingerprint: dict[str, list[Transaction]] = {}
    for transaction in existing:
        if transaction.external_reference:
            key = (
                _reference_key(transaction.external_reference), transaction.transaction_date,
                transaction.transaction_type, transaction.amount_paise,
            )
            by_ref.setdefault(key, []).append(transaction)
        by_fingerprint.setdefault(transaction.duplicate_fingerprint, []).append(transaction)

    local_refs: dict[tuple, Transaction] = {}
    local_fingerprints: dict[str, Transaction] = {}
    for row_number, item in records:
        merchant = normalize_merchant(item.normalized_merchant) if item.normalized_merchant else None
        amount_paise = rupees_to_paise(item.amount)
        fingerprint = duplicate_fingerprint(item.transaction_date, item.transaction_type, item.amount, item.description)
        reference_key = _reference_key(item.external_reference)
        reference_lookup = (reference_key, item.transaction_date, item.transaction_type, amount_paise) if reference_key else None
        matched = by_ref.get(reference_lookup, [])[-1] if reference_lookup and by_ref.get(reference_lookup) else None
        duplicate_status = "duplicate" if matched else "none"
        duplicate_reason = (
            f"External reference {item.external_reference} matches an existing row with the same date, amount, and direction."
            if matched else None
        )
        if not matched and not (reference_key and any(
            _reference_key(t.external_reference) and _reference_key(t.external_reference) != reference_key
            for t in by_fingerprint.get(fingerprint, [])
        )):
            probable = local_fingerprints.get(fingerprint) or (by_fingerprint.get(fingerprint) or [None])[0]
            if probable is not None and (not reference_key or not probable.external_reference):
                duplicate_status = "probable_duplicate"
                duplicate_reason = "Same date, direction, amount, and narration fingerprint; no matching external reference is available."

        prediction = categorize(item.description, merchant, db)
        transaction_id = str(uuid.uuid4())
        transaction = Transaction(
            id=transaction_id, transaction_date=item.transaction_date,
            raw_narration=item.description, cleaned_description=clean_description(item.description),
            normalized_merchant=merchant, amount_paise=amount_paise, currency=item.currency,
            transaction_type=item.transaction_type, category=prediction.category,
            confidence_score=prediction.confidence_score, category_explanation=prediction.reason,
            source_format=source_format, duplicate_status=duplicate_status,
            duplicate_fingerprint=fingerprint, external_reference=item.external_reference,
            original_raw_transaction_text=item.raw_text, import_batch_id=batch.id, user_locked=False,
        )
        db.add(transaction)
        db.add(ImportRow(
            id=str(uuid.uuid4()), batch_id=batch.id, row_number=row_number,
            status=duplicate_status, message=duplicate_reason, raw_source_text=item.raw_text,
            transaction_id=transaction_id,
        ))
        batch.imported_count += 1
        if duplicate_status == "duplicate":
            batch.duplicate_count += 1
        elif duplicate_status == "probable_duplicate":
            batch.probable_duplicate_count += 1
        if prediction.category == "Review Required":
            batch.review_required_count += 1
        local_fingerprints[fingerprint] = transaction
        if reference_lookup:
            local_refs[reference_lookup] = transaction
            by_ref.setdefault(reference_lookup, []).append(transaction)
        by_fingerprint.setdefault(fingerprint, []).append(transaction)

    for error in errors:
        db.add(ImportRow(
            id=str(uuid.uuid4()), batch_id=batch.id, row_number=error.row_number,
            status="rejected", message=error.error, raw_source_text=error.raw_text,
        ))
    for row_number, message, raw_text in review_rows or []:
        db.add(ImportRow(
            id=str(uuid.uuid4()), batch_id=batch.id, row_number=row_number,
            status="needs_review", message=message, raw_source_text=raw_text,
        ))
        batch.review_required_count += 1
    for row_number, message, raw_text in ignored_rows or []:
        db.add(ImportRow(
            id=str(uuid.uuid4()), batch_id=batch.id, row_number=row_number,
            status="ignored", message=message, raw_source_text=raw_text,
        ))
    db.commit()
    db.refresh(batch)
    return batch


def classify_sms_duplicate(db: Session, fingerprint: str, external_reference: str | None):
    # Shared by SMS import; no amount-only match can pass this fingerprint check.
    normalized_ref = _reference_key(external_reference)
    if normalized_ref:
        candidates = db.scalars(select(Transaction).where(Transaction.external_reference.is_not(None))).all()
        for transaction in candidates:
            if _reference_key(transaction.external_reference) == normalized_ref:
                return "duplicate", f"External reference {external_reference} was imported previously."
    existing = db.scalar(select(Transaction).where(Transaction.duplicate_fingerprint == fingerprint))
    if existing:
        return "probable_duplicate", "Same date, direction, amount, and narration fingerprint; no matching external reference is available."
    return "none", None
