from __future__ import annotations

import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pdfplumber

CENT = Decimal("0.01")
MAX_ROWS = 10_000
MAX_PDF_PAGES = 150


def money(value: object) -> Decimal:
    raw = str(value or "").strip().replace("₹", "").replace("INR", "")
    if not raw:
        raise ValueError("Amount is missing")
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("() ").replace(",", "").replace(" ", "")
    try:
        result = Decimal(raw)
    except InvalidOperation as error:
        raise ValueError("Amount is not a valid number") from error
    if not result.is_finite():
        raise ValueError("Amount must be finite")
    if negative:
        result = -result
    return result.quantize(CENT, rounding=ROUND_HALF_UP)


def normalize_date(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Transaction date is missing")
    candidates = (raw, raw[:10])
    formats = (
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
        "%d-%b-%Y", "%d %b %Y", "%Y/%m/%d", "%m/%d/%Y",
    )
    for candidate in candidates:
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt).date().isoformat()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Date must be a supported calendar date (for example, 2026-11-21)")


def merchant_from_text(raw_text: str) -> str:
    text = raw_text.upper()
    match = re.search(r"UPI/\d+/(?:DR|CR)?/?([A-Z0-9\s.\-]+?)(?:/|@|$)", text)
    if match:
        name = match.group(1).strip()
        if len(name) >= 3:
            return name[:48]
    match = re.search(r"(?:TO|AT|TOWARDS)\s+([A-Z0-9 .&'-]{2,48}?)(?:\s+(?:ON|REF|UTR|UPI)|$)", text)
    if match:
        return match.group(1).strip(" .")[:48]
    words = re.sub(r"[^A-Z0-9 ]", " ", text).split()
    ignored = {"UPI", "POS", "IMPS", "NEFT", "DEBIT", "CREDIT", "PAID", "FROM", "BANK", "ACCT", "INR", "RS"}
    found = [word for word in words if len(word) > 2 and word not in ignored]
    return " ".join(found[:3])[:48] if found else "UNKNOWN MERCHANT"


def is_credit(raw_text: str, explicit_direction: str = "") -> bool:
    direction = explicit_direction.strip().upper()
    if direction in {"CR", "CREDIT", "DEPOSIT", "RECEIVED", "IN"}:
        return True
    if direction in {"DR", "DEBIT", "WITHDRAWAL", "OUT"}:
        return False
    return bool(re.search(r"\b(credited|received|deposited|refund(ed)?)\b|\bCR\b", raw_text, re.I))


def quarantined(raw_text: str) -> str | None:
    patterns = ("ignore all rules", "ignore previous", "system prompt", "mark this as", "you are now", "override instructions")
    lower = raw_text.lower()
    for pattern in patterns:
        if pattern in lower:
            return f"QUARANTINED_INJECTION ('{pattern}' removed from categorization input)"
    return None


def clean_untrusted(raw_text: str) -> str:
    return re.sub(r"(?i)(ignore all rules.*|ignore previous.*|system prompt.*|mark this as.*|you are now.*|override instructions.*)", "", raw_text).strip()


def _record(day: str | None, raw: str, amount: Decimal, direction: str, source: str) -> dict:
    return {
        "date": day,
        "raw_narration": raw.strip(),
        "merchant": merchant_from_text(clean_untrusted(raw)),
        "amount": amount,
        "txn_type": direction,
        "source": source,
        "security_flag": quarantined(raw),
        "requires_review": day is None,
    }


def sms_preview(sms_text: str) -> dict:
    lines = [line.strip() for line in sms_text.splitlines() if line.strip()]
    records: list[dict] = []
    issues: list[dict] = []
    ignored = 0
    noise = re.compile(r"\b(OTP|one time password|promotional|pre-approved|offer|cashback|do not share|available balance|account balance|avl bal|bal only|balance enquiry)\b", re.I)
    amount_pattern = re.compile(r"(?:₹|INR\s*|Rs\.?\s*)([\d,]+(?:\.\d{1,2})?)", re.I)
    amount_fallback = re.compile(r"\b(?:debited|credited|spent|paid|received|withdrawn)\s+(?:by\s+)?(?:₹|INR\s*|Rs\.?\s*)?([\d,]+(?:\.\d{1,2})?)", re.I)
    for index, line in enumerate(lines, start=1):
        if noise.search(line):
            ignored += 1
            continue
        match = amount_pattern.search(line) or amount_fallback.search(line)
        if not match:
            if re.search(r"\b(balance|bal)\b", line, re.I):
                ignored += 1
            else:
                issues.append({"row": index, "message": "No recognizable transaction amount; message was not imported."})
            continue
        try:
            amount = money(match.group(1))
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
        except ValueError as error:
            issues.append({"row": index, "message": str(error)})
            continue
        date_match = re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b", line)
        try:
            txn_date = normalize_date(date_match.group(1)) if date_match else None
        except ValueError as error:
            issues.append({"row": index, "message": str(error)})
            txn_date = None
        records.append(_record(txn_date, line, amount, "CREDIT" if is_credit(line) else "DEBIT", "SMS"))
        if txn_date is None:
            issues.append({"row": index, "message": "Date was not present; choose a transaction date before confirming this row."})
    return {"transactions": records, "ignored": ignored, "issues": issues, "rows_seen": len(lines)}


def _header_key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value).replace("\ufeff", "").strip().lower()).strip()


def csv_preview(data: bytes) -> dict:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        return {"transactions": [], "ignored": 0, "issues": [{"row": 1, "message": "CSV must use UTF-8 or UTF-8-SIG encoding."}], "rows_seen": 0}
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return {"transactions": [], "ignored": 0, "issues": [{"row": 1, "message": "CSV header row is missing."}], "rows_seen": 0}
    keys = {_header_key(name): name for name in reader.fieldnames}
    date_col = next((v for k, v in keys.items() if k in {"date", "transaction date", "txn date", "value date", "posting date"} or k.endswith(" date")), None)
    desc_col = next((v for k, v in keys.items() if any(token in k for token in ("narration", "description", "particular", "remark", "merchant", "transaction details", "reference"))), None)
    debit_col = next((v for k, v in keys.items() if k in {"debit", "debit amount", "withdrawal", "withdrawals", "dr", "dr amount", "paid out"}), None)
    credit_col = next((v for k, v in keys.items() if k in {"credit", "credit amount", "deposit", "deposits", "cr", "cr amount", "paid in"}), None)
    amount_col = next((v for k, v in keys.items() if k in {"amount", "transaction amount", "txn amount", "amt"}), None)
    direction_col = next((v for k, v in keys.items() if k in {"type", "dr cr", "dr cr indicator", "transaction type", "txn type", "debit credit"}), None)
    missing = [name for name, found in (("date", date_col), ("narration/description", desc_col)) if not found]
    if not (debit_col or credit_col or amount_col):
        missing.append("debit, credit, or amount column")
    if missing:
        return {"transactions": [], "ignored": 0, "issues": [{"row": 1, "message": "Required CSV columns not found: " + ", ".join(missing)}], "rows_seen": 0}

    records: list[dict] = []
    issues: list[dict] = []
    rows_seen = 0
    for row_number, row in enumerate(reader, start=2):
        rows_seen += 1
        if rows_seen > MAX_ROWS:
            issues.append({"row": row_number, "message": f"CSV exceeds the {MAX_ROWS:,}-row import limit."})
            break
        raw = str(row.get(desc_col, "") or "").strip()
        try:
            if not raw:
                raise ValueError("Description is missing")
            day = normalize_date(row.get(date_col, ""))
            debit_raw = row.get(debit_col, "") if debit_col else ""
            credit_raw = row.get(credit_col, "") if credit_col else ""
            debit = money(debit_raw) if str(debit_raw or "").strip() else Decimal("0.00")
            credit = money(credit_raw) if str(credit_raw or "").strip() else Decimal("0.00")
            if debit < 0 or credit < 0:
                raise ValueError("Debit and credit columns must contain positive amounts")
            if debit and credit:
                raise ValueError("A row cannot have both debit and credit amounts")
            if debit or credit:
                amount, direction = (debit, "DEBIT") if debit else (credit, "CREDIT")
            elif amount_col:
                amount = money(row.get(amount_col, ""))
                explicit_direction = str(row.get(direction_col, "") if direction_col else "").strip()
                direction = "CREDIT" if is_credit(raw, explicit_direction) else "DEBIT"
                if amount < 0:
                    amount = abs(amount)
                    if not explicit_direction:
                        direction = "DEBIT"
            else:
                raise ValueError("Amount is missing")
            if amount <= 0:
                raise ValueError("Amount must be greater than zero")
            records.append(_record(day, raw, amount, direction, "CSV"))
        except ValueError as error:
            issues.append({"row": row_number, "message": str(error)})
    return {"transactions": records, "ignored": 0, "issues": issues, "rows_seen": rows_seen}


def pdf_preview(data: bytes) -> dict:
    records: list[dict] = []
    issues: list[dict] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                return {"transactions": [], "ignored": 0, "issues": [{"row": 1, "message": f"PDF exceeds the {MAX_PDF_PAGES}-page limit."}], "rows_seen": 0}
            row_number = 0
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text() or ""
                for line in page_text.splitlines():
                    row_number += 1
                    match = re.search(r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}-\d{2}-\d{2})\s+(.+?)\s+([\d,]+(?:\.\d{1,2})?)\s*(DR|CR)?$", line.strip(), re.I)
                    if not match:
                        continue
                    raw_date, raw_description, raw_amount, marker = match.groups()
                    try:
                        day = normalize_date(raw_date)
                        amount = money(raw_amount)
                        if amount <= 0 or not raw_description.strip():
                            raise ValueError("Date, description and a positive amount are required")
                        direction = "CREDIT" if (marker or "").upper() == "CR" else "DEBIT"
                        records.append(_record(day, raw_description, amount, direction, "PDF"))
                    except ValueError as error:
                        issues.append({"row": row_number, "message": f"Page {page_number}: {error}"})
                if not page_text.strip():
                    issues.append({"row": page_number, "message": f"Page {page_number} has no extractable text. Scanned PDFs are not supported."})
    except Exception as error:
        return {"transactions": [], "ignored": 0, "issues": [{"row": 1, "message": f"Could not read PDF: {type(error).__name__}. Check that it is a valid, unencrypted PDF."}], "rows_seen": 0}
    return {"transactions": records, "ignored": 0, "issues": issues, "rows_seen": row_number if 'row_number' in locals() else 0}


def transaction_fingerprint(item: dict) -> str:
    raw = " ".join(str(item.get("raw_narration", "")).upper().split())
    merchant = " ".join(str(item.get("merchant", "")).upper().split())
    canonical = "|".join((str(item.get("date") or ""), str(item.get("amount") or ""), str(item.get("txn_type") or ""), merchant, raw))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_csv_bytes(data: bytes) -> list[dict]:
    return csv_preview(data)["transactions"]


def parse_pdf_bytes(data: bytes) -> list[dict]:
    return pdf_preview(data)["transactions"]


def parse_sms_dump(sms_text: str) -> tuple[list[dict], int]:
    result = sms_preview(sms_text)
    return result["transactions"], result["ignored"] + len(result["issues"])
