from __future__ import annotations

import csv
import io
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pdfplumber
from sqlalchemy import select

from ingestion import create_batch
from models import ImportRow, LearnedCategoryRule, Transaction
from parsers.csv_importer import CsvFormatError, parse_csv_bytes
from parsers.pdf_importer import PdfImportError, ScannedPdfError, parse_pdf
from parsers.sms_parser import parse_sms
from transaction_engine.categorizer import categorize
from transaction_engine.fingerprint import duplicate_fingerprint
from transaction_engine.money import paise_to_rupees, rupees_to_paise
from transaction_engine.merchant import normalize_merchant


def test_integer_paise_uses_decimal_rounding() -> None:
    assert rupees_to_paise(Decimal("123456.70")) == 12_345_670
    assert rupees_to_paise("0.01") == 1
    assert paise_to_rupees(12_345_670) == Decimal("123456.70")


def test_csv_utf8_sig_variations_and_indian_amount() -> None:
    content = (
        "\ufeffTransaction Date,Description,Amount,Dr/Cr,UTR\n"
        '01/11/2026,"UPI/PAYTMQR/CAFE INDIGO",₹1,25,000.50,DR,SYN-UTR-1\n'
    ).encode("utf-8-sig")
    # Quote the Indian-formatted amount field because its thousands separator is a CSV delimiter.
    content = content.replace(b"\xe2\x82\xb91,25,000.50", b'"\xe2\x82\xb91,25,000.50"')
    records, errors = parse_csv_bytes(content)
    assert not errors
    assert len(records) == 1
    _, row = records[0]
    assert row.transaction_date == date(2026, 11, 1)
    assert row.amount == Decimal("125000.50")
    assert row.transaction_type == "debit"
    assert row.external_reference == "SYN-UTR-1"
    assert normalize_merchant(row.normalized_merchant) == "cafe indigo"


def test_csv_separate_debit_credit_and_single_amount_aliases() -> None:
    content = (
        "Txn Date,Particulars,Withdrawal,Deposit\n"
        "02-11-2026,UPI BigBasket,1250.25,\n"
        "03-11-2026,SALARY CREDIT,,45000\n"
    ).encode()
    records, errors = parse_csv_bytes(content)
    assert not errors
    assert [(row.transaction_type, row.amount) for _, row in records] == [
        ("debit", Decimal("1250.25")), ("credit", Decimal("45000.00"))
    ]


def test_csv_rejects_invalid_rows_and_unsupported_headers() -> None:
    content = (
        "Date,Narration,Amount,Type\n"
        "2026-11-01,UPI Grocery,100,DEBIT\n"
        "not-a-date,UPI Grocery,100,DEBIT\n"
        "2026-11-03,,200,DEBIT\n"
        "2026-11-04,Unknown item,NaN,\n"
        "2026-11-05,Unclear item,200,\n"
    ).encode()
    records, errors = parse_csv_bytes(content)
    assert len(records) == 1
    assert [error.row_number for error in errors] == [3, 4, 5, 6]
    assert "invalid transaction date" in errors[0].error
    assert "description" in errors[1].error
    assert "invalid amount" in errors[2].error
    assert "direction is ambiguous" in errors[3].error
    try:
        parse_csv_bytes(b"Foo,Bar\na,b\n")
    except CsvFormatError as exc:
        assert "Unsupported CSV format" in str(exc)
    else:
        raise AssertionError("unsupported header should be rejected")


def test_categories_have_explanations_and_unknowns_require_review(db) -> None:
    grocery = categorize("UPI BigBasket grocery", "BigBasket", db)
    assert grocery.category == "Groceries"
    assert grocery.confidence_score >= 0.8
    assert "keyword" in grocery.reason
    unknown = categorize("UPI/839201/PAYTMQR/merchant", "merchant", db)
    assert unknown.category == "Review Required"
    assert unknown.confidence_score < 0.5


def test_saved_rule_precedes_generic_rule(db) -> None:
    db.add(LearnedCategoryRule(id="rule-1", merchant_key="netflix", category="Groceries"))
    db.commit()
    prediction = categorize("Netflix subscription payment", "Netflix", db)
    assert prediction.category == "Groceries"
    assert "saved merchant rule" in prediction.reason


def test_duplicate_fingerprint_uses_narration_not_amount_only() -> None:
    first = duplicate_fingerprint(date(2026, 11, 1), "debit", Decimal("500.00"), "UPI Cafe Indigo ref 1")
    same_amount_other_purchase = duplicate_fingerprint(date(2026, 11, 1), "debit", Decimal("500.00"), "UPI Grocery ref 2")
    assert first != same_amount_other_purchase


SMS_CASES = [
    ("Paid Rs. 499 to Netflix on 02-11-2026", "debit", 49_900, "netflix"),
    ("INR 250 debited for UPI transaction on 03-11-2026 Ref: SYN12345678", "debit", 25_000, None),
    ("Salary credited Rs. 45000 on 04-11-2026", "credit", 4_500_000, None),
    ("UPI/PAYTMQR/CAFE INDIGO paid Rs. 320 on 05-11-2026", "debit", 32_000, "cafe indigo"),
    ("Rs. 2,000 withdrawn from ATM on 06-11-2026", "debit", 200_000, None),
    ("NEFT transfer to Rahul Sharma INR 1,200 debited on 07-11-2026", "debit", 120_000, "rahul sharma"),
]


def test_sms_indian_transaction_patterns() -> None:
    for text, direction, amount_paise, merchant in SMS_CASES:
        parsed = parse_sms(text)
        assert parsed.transaction_type == direction, text
        assert rupees_to_paise(parsed.amount) == amount_paise, text
        assert parsed.transaction_date is not None, text
        assert parsed.normalized_merchant == merchant, text


def test_sms_never_invents_fields_and_flags_otp_promo() -> None:
    incomplete = parse_sms("UPI payment debited but details unavailable")
    assert incomplete.amount is None
    assert incomplete.transaction_date is None
    assert incomplete.needs_review
    assert "amount" in incomplete.missing_fields
    otp = parse_sms("Your OTP is 778811. Do not share it.")
    assert otp.ignored_reason == "OTP/security message"
    promo = parse_sms("Limited time offer, click here for a discount")
    assert promo.ignored_reason == "promotional message"


def _make_table_pdf(balance_second: str = "55000.00") -> bytes:
    xs = [20, 90, 330, 400, 470, 570]
    ys = [690, 670, 650, 630]
    commands = ["0.5 w"]
    for y in ys:
        commands.append(f"{xs[0]} {y} m {xs[-1]} {y} l S")
    for x in xs:
        commands.append(f"{x} {ys[-1]} m {x} {ys[0]} l S")
    rows = [
        ["Date", "Narration", "Debit", "Credit", "Balance"],
        ["01/11/2026", "UPI Grocery", "500.00", "", "10000.00"],
        ["02/11/2026", "Salary credited", "", "45000.00", balance_second],
    ]
    for row_index, row in enumerate(rows):
        y = [676, 656, 636][row_index]
        for col_index, text in enumerate(row):
            if text:
                escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.append(f"BT /F1 9 Tf {xs[col_index] + 4} {y} Td ({escaped}) Tj ET")
    stream = "\n".join(commands).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 750] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


def test_pdf_supported_text_table_and_balance_reconciliation() -> None:
    content = _make_table_pdf()
    # Exercise actual pdfplumber table extraction, not a mocked parser result.
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        assert len(pdf.pages[0].extract_tables()) == 1
    parsed = parse_pdf(content)
    assert len(parsed.records) == 2
    assert parsed.errors == []
    assert parsed.balance_reconciliation == {"status": "reconciled", "checked_rows": 1, "discrepancies": []}


def test_pdf_balance_mismatch_and_scanned_or_unsupported_pdf() -> None:
    mismatch = parse_pdf(_make_table_pdf("56000.00"))
    assert mismatch.balance_reconciliation["status"] == "mismatch"
    assert mismatch.warnings
    try:
        parse_pdf(b"%PDF-1.4\n%%EOF")
    except (ScannedPdfError, PdfImportError):
        pass
    else:
        raise AssertionError("malformed/scanned PDF should be rejected")


def _csv(rows: list[list[str]], headers=None) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(headers or ["Date", "Narration", "Amount", "Type", "UTR"])
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def test_csv_api_import_duplicate_counts_and_batch_details(client) -> None:
    content = _csv([
        ["2026-11-01", "UPI BigBasket grocery", "₹1,25,000.50", "DR", "UTR-1"],
        ["2026-11-02", "UPI BigBasket grocery", "500", "DR", "UTR-2"],
        ["2026-11-03", "UPI Unknown merchant", "700", "DR", "UTR-3"],
        ["bad-date", "UPI Cafe", "100", "DR", "UTR-4"],
    ])
    first = client.post("/api/transactions/import/csv", files={"file": ("fixture.csv", content, "text/csv")})
    assert first.status_code == 200, first.text
    summary = first.json()
    assert summary["imported_count"] == 3
    assert summary["rejected_count"] == 1
    assert summary["review_required_count"] == 1
    assert summary["duplicate_count"] == 0
    assert summary["rows"][-1]["status"] == "rejected"
    assert summary["rows"][-1]["raw_source_text"]

    repeated = client.post("/api/transactions/import/csv", files={"file": ("fixture.csv", content, "text/csv")})
    assert repeated.status_code == 200
    assert repeated.json()["duplicate_count"] == 3
    assert repeated.json()["probable_duplicate_count"] == 0
    batch_id = repeated.json()["batch_id"]
    details = client.get(f"/api/import-batches/{batch_id}")
    assert details.status_code == 200
    assert details.json()["duplicate_count"] == 3

    listed = client.get("/api/transactions")
    assert listed.status_code == 200
    assert all(item["duplicate_status"] != "duplicate" for item in listed.json()["items"])
    all_rows = client.get("/api/transactions?include_duplicates=true")
    assert all_rows.json()["total"] == 6
    assert any(item["amount_paise"] == 12500050 for item in all_rows.json()["items"])


def test_identical_amount_distinct_purchases_and_probable_duplicate(client) -> None:
    content = _csv([
        ["2026-11-01", "Cafe Indigo", "500", "DR", "REF-1"],
        ["2026-11-01", "Grocery Store", "500", "DR", "REF-2"],
    ])
    first = client.post("/api/transactions/import/csv", files={"file": ("two.csv", content, "text/csv")})
    assert first.json()["imported_count"] == 2
    assert first.json()["duplicate_count"] == 0

    no_ref = _csv([["2026-11-04", "Neighborhood Bookstall", "540", "DR", ""]])
    one = client.post("/api/transactions/import/csv", files={"file": ("single.csv", no_ref, "text/csv")})
    again = client.post("/api/transactions/import/csv", files={"file": ("single.csv", no_ref, "text/csv")})
    assert one.json()["probable_duplicate_count"] == 0
    assert again.json()["probable_duplicate_count"] == 1
    assert again.json()["duplicate_count"] == 0


def test_sms_preview_and_import_api(client) -> None:
    text = "Paid Rs. 499 to Netflix on 02-11-2026 Ref: UTR12345678"
    preview = client.post("/api/transactions/parse-sms", json={"text": text})
    assert preview.status_code == 200
    assert preview.json()["amount_paise"] == 49900
    assert preview.json()["transaction_type"] == "debit"

    response = client.post("/api/transactions/import/sms", json={"messages": [
        "Paid Rs. 499 to Netflix on 02-11-2026 Ref: UTR12345678",
        "Your OTP is 993322. Do not share it.",
        "UPI payment debited but date and amount unavailable",
    ]})
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["imported_count"] == 1
    assert summary["ignored_count"] == 1
    assert summary["review_required_count"] == 1
    assert {row["status"] for row in summary["rows"]} == {"imported", "ignored", "needs_review"}


def test_category_correction_preview_locks_rule_and_future_match(client):
    content = _csv([
        ["2026-11-01", "Cafe Indigo", "500", "DR", "CAFE-1"],
        ["2026-11-02", "Cafe Indigo", "600", "DR", "CAFE-2"],
        ["2026-11-03", "Cafe Indigo", "700", "DR", "CAFE-3"],
    ])
    imported = client.post("/api/transactions/import/csv", files={"file": ("cafe.csv", content, "text/csv")})
    assert imported.status_code == 200
    ids = [item["id"] for item in client.get("/api/transactions").json()["items"]]

    # Lock one matching transaction with a different correction.
    locked = client.patch(f"/api/transactions/{ids[0]}/category", json={"category": "Shopping"})
    assert locked.status_code == 200
    preview = client.post(f"/api/transactions/{ids[1]}/category/preview", json={
        "category": "Food & Dining", "apply_to_matching": True,
    })
    assert preview.status_code == 200
    assert preview.json()["eligible_count"] == 2
    assert preview.json()["locked_count"] == 1

    corrected = client.patch(f"/api/transactions/{ids[1]}/category", json={
        "category": "Food & Dining", "apply_to_matching": True,
    })
    assert corrected.status_code == 200
    assert corrected.json()["rule_applied_to_existing_count"] == 1
    assert corrected.json()["locked_transactions_skipped"] == 1
    assert len(corrected.json()["updated_transaction_ids"]) == 2

    transactions = {item["id"]: item for item in client.get("/api/transactions").json()["items"]}
    assert transactions[ids[0]]["category"] == "Shopping"
    assert transactions[ids[0]]["user_locked"] is True
    assert transactions[ids[1]]["category"] == "Food & Dining"
    assert transactions[ids[2]]["category"] == "Food & Dining"

    rules = client.get("/api/rules")
    assert rules.status_code == 200
    assert any(rule["merchant_key"] == "cafe indigo" and rule["category"] == "Food & Dining" for rule in rules.json())

    future = _csv([["2026-11-10", "Cafe Indigo", "250", "DR", "CAFE-FUTURE"]])
    future_result = client.post("/api/transactions/import/csv", files={"file": ("future.csv", future, "text/csv")})
    assert future_result.status_code == 200
    newest = client.get("/api/transactions").json()["items"][0]
    assert newest["category"] == "Food & Dining"
    assert "saved merchant rule" in newest["category_explanation"]


def test_health_and_validation_api(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok", "database": "ok"}
    unsupported = client.post(
        "/api/transactions/import/csv",
        files={"file": ("bad.csv", b"foo,bar\na,b\n", "text/csv")},
    )
    assert unsupported.status_code == 422
    assert "Unsupported CSV format" in unsupported.json()["detail"]
    not_found = client.get("/api/import-batches/no-such-batch")
    assert not_found.status_code == 404


def test_synthetic_fixture_has_at_least_30_rows_and_labels() -> None:
    fixture = Path(__file__).resolve().parents[2] / "sample_data" / "transactions_synthetic.csv"
    with fixture.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) >= 30
    assert {row["Ground Truth Category"] for row in rows} >= {
        "Food & Dining", "Groceries", "Transport", "Shopping", "Subscriptions",
        "Rent", "Salary / Income", "Transfers", "Review Required",
    }
    assert sum(row["UTR"] == "SYN-REF-0018" for row in rows) == 2
