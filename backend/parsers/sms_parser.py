from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from transaction_engine.categorizer import CategoryPrediction, categorize
from transaction_engine.merchant import normalize_merchant
from parsers.csv_importer import _parse_date

_AMOUNT_RE = re.compile(r"(?:₹|\bINR\b|\bRs\.?\s*)\s*([+-]?\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b"
)
_OTP_RE = re.compile(r"\b(?:otp|one[ -]time password|verification code)\b", re.IGNORECASE)
_PROMO_RE = re.compile(r"\b(?:offer|cashback|win a|limited time|click here|promo code|discount)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParsedSms:
    raw_text: str
    transaction_date: date | None
    description: str
    normalized_merchant: str | None
    amount: Decimal | None
    transaction_type: str | None
    category: CategoryPrediction
    missing_fields: tuple[str, ...]
    external_reference: str | None = None
    ignored_reason: str | None = None

    @property
    def needs_review(self) -> bool:
        return bool(self.missing_fields) and self.ignored_reason is None


def _parse_amount(text: str) -> Decimal | None:
    match = _AMOUNT_RE.search(text)
    if not match:
        return None
    try:
        amount = Decimal(match.group(1).replace(",", ""))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount == 0 or abs(amount.as_tuple().exponent) > 2:
        return None
    return abs(amount).quantize(Decimal("0.01"))


def _parse_direction(text: str) -> str | None:
    lowered = text.casefold()
    if re.search(r"\b(credited|credit|salary received|salary credited|deposited|received)\b", lowered):
        return "credit"
    if re.search(r"\b(debited|debit|paid|purchase|withdrawal|withdrawn|spent)\b", lowered):
        return "debit"
    return None


def _extract_merchant(text: str) -> str | None:
    patterns = (
        r"\bpaid\s+(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d{1,2})?\s+to\s+([^,.;\n]+)",
        r"\b(?:sent|transferred)\s+(?:rs\.?|inr|₹)?\s*[\d,]+(?:\.\d{1,2})?\s+to\s+([^,.;\n]+)",
        r"\b(?:neft|imps|rtgs)\s+(?:transfer\s+)?to\s+([^,.;\n]+)",
        r"\b(?:at|to)\s+([A-Za-z][A-Za-z0-9 &._'-]{1,50})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = re.split(r"\s+(?:on|ref|txn|utr)\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
            return normalize_merchant(value)

    if re.search(r"\b(?:salary|atm withdrawal|cash withdrawal|upi transaction)\b", text, re.IGNORECASE):
        return None
    upi = re.search(r"\bUPI[/: -]+(.+)", text, re.IGNORECASE)
    if upi:
        return normalize_merchant(upi.group(1))
    return None


def parse_sms(text: str, db=None) -> ParsedSms:
    raw = text.strip()
    if not raw:
        return ParsedSms(raw, None, raw, None, None, None, categorize(raw, None, db), ("message",))
    if _OTP_RE.search(raw):
        return ParsedSms(raw, None, raw, None, None, None, categorize(raw, None, db), (), ignored_reason="OTP/security message")
    if _PROMO_RE.search(raw) and not _AMOUNT_RE.search(raw):
        return ParsedSms(raw, None, raw, None, None, None, categorize(raw, None, db), (), ignored_reason="promotional message")

    amount = _parse_amount(raw)
    direction = _parse_direction(raw)
    date_match = _DATE_RE.search(raw)
    txn_date = None
    if date_match:
        try:
            txn_date = _parse_date(date_match.group(0))
        except ValueError:
            txn_date = None
    merchant = _extract_merchant(raw)
    reference_match = re.search(r"\b(?:UTR|RRN|REF(?:ERENCE)?|TXN\s*ID)\s*[:#-]?\s*([A-Z0-9-]{6,})", raw, re.IGNORECASE)
    external_reference = reference_match.group(1) if reference_match else None
    prediction = categorize(raw, merchant, db)
    missing = []
    if amount is None:
        missing.append("amount")
    if direction is None:
        missing.append("debit/credit direction")
    if txn_date is None:
        missing.append("transaction date")
    return ParsedSms(raw, txn_date, raw, merchant, amount, direction, prediction, tuple(missing), external_reference)
