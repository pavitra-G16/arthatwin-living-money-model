from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from transaction_engine.merchant import normalize_merchant

HEADER_ALIASES = {
    "date": ("date", "transaction date", "txn date", "trans date", "value date", "posting date"),
    "description": ("narration", "description", "details", "particulars", "transaction details", "remarks", "transaction particulars"),
    "merchant": ("merchant", "payee", "beneficiary", "counterparty"),
    "amount": ("amount", "transaction amount", "txn amount", "transaction amt", "value"),
    "debit": ("debit", "debit amount", "withdrawal", "withdrawals", "withdrawal amt", "paid out"),
    "credit": ("credit", "credit amount", "deposit", "deposits", "deposit amount", "paid in"),
    "direction": ("type", "transaction type", "dr cr", "dr/cr", "direction", "transaction direction"),
    "currency": ("currency", "ccy"),
    "external_reference": ("reference", "reference number", "ref", "ref no", "utr", "rrn", "upi ref", "transaction id", "txn id"),
}


class CsvFormatError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedCsvTransaction:
    transaction_date: date
    description: str
    normalized_merchant: str | None
    amount: Decimal
    transaction_type: str
    currency: str
    raw_text: str
    external_reference: str | None = None


@dataclass(frozen=True)
class RowError:
    row_number: int
    error: str
    raw_text: str = ""


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lstrip("\ufeff").casefold()).strip()


def _parse_date(value: str) -> date:
    candidate = value.strip()
    if not candidate:
        raise ValueError("transaction date is missing")
    try:
        return datetime.fromisoformat(candidate.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(candidate, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"invalid transaction date '{candidate}' (use YYYY-MM-DD or DD/MM/YYYY)")


def _parse_money(value: str) -> Decimal:
    candidate = value.strip().replace("₹", "").replace("INR", "").replace("inr", "").replace("Rs.", "").replace("Rs", "")
    candidate = candidate.replace(",", "").replace(" ", "")
    if not candidate:
        raise ValueError("amount is missing")
    negative = candidate.startswith("(") and candidate.endswith(")")
    if negative:
        candidate = candidate[1:-1]
    try:
        amount = Decimal(candidate)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount '{value}'") from exc
    if not amount.is_finite():
        raise ValueError(f"invalid amount '{value}' (must be finite)")
    if amount == 0:
        raise ValueError("amount must be non-zero")
    if abs(amount.as_tuple().exponent) > 2:
        raise ValueError("amount must have no more than two decimal places")
    if negative:
        amount = -amount
    return abs(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * (-1 if amount < 0 else 1)


def _direction(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().casefold().replace(".", "")
    if normalized in {"dr", "d", "debit", "withdrawal", "withdraw", "paid", "outflow"}:
        return "debit"
    if normalized in {"cr", "c", "credit", "deposit", "received", "inflow"}:
        return "credit"
    return None


def _infer_direction(description: str) -> str | None:
    text = description.casefold()
    if re.search(r"\b(credited|credit|salary|received|deposit|refund)\b", text):
        return "credit"
    if re.search(r"\b(debited|debit|paid|purchase|withdrawal|rent|upi|pos|subscription|payment)\b", text):
        return "debit"
    return None


def _get(row: dict, original_header: str | None) -> str:
    if original_header is None:
        return ""
    value = row.get(original_header, "")
    return str(value or "").strip()


def parse_csv_bytes(content: bytes) -> tuple[list[tuple[int, ParsedCsvTransaction]], list[RowError]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CsvFormatError("File must be UTF-8 or UTF-8-SIG encoded.") from exc
    if not text.strip():
        raise CsvFormatError("CSV file is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise CsvFormatError("CSV header row is missing.")

    normalized_headers = {_header_key(header): header for header in reader.fieldnames if header}
    columns: dict[str, str | None] = {}
    for field, aliases in HEADER_ALIASES.items():
        columns[field] = next((normalized_headers[_header_key(alias)] for alias in aliases if _header_key(alias) in normalized_headers), None)

    missing = []
    if columns["date"] is None:
        missing.append("date")
    if columns["description"] is None:
        missing.append("narration/description")
    if columns["amount"] is None and columns["debit"] is None and columns["credit"] is None:
        missing.append("amount or debit/credit column")
    if missing:
        raise CsvFormatError("Unsupported CSV format; missing required column(s): " + ", ".join(missing) + ".")

    parsed: list[tuple[int, ParsedCsvTransaction]] = []
    errors: list[RowError] = []
    try:
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                errors.append(RowError(row_number, "row has more values than the header"))
                continue
            try:
                description = _get(row, columns["description"])
                if not description:
                    raise ValueError("description/narration is missing")
                txn_date = _parse_date(_get(row, columns["date"]))
                debit_raw = _get(row, columns["debit"])
                credit_raw = _get(row, columns["credit"])
                amount_raw = _get(row, columns["amount"])
                declared_direction = _direction(_get(row, columns["direction"]))

                if (debit_raw or credit_raw) and (columns["debit"] or columns["credit"]):
                    debit = _parse_money(debit_raw) if debit_raw else Decimal("0")
                    credit = _parse_money(credit_raw) if credit_raw else Decimal("0")
                    debit, credit = abs(debit), abs(credit)
                    if debit and credit:
                        raise ValueError("both debit and credit amounts are set")
                    if not debit and not credit:
                        raise ValueError("debit/credit amount is missing or zero")
                    amount, txn_type = (debit, "debit") if debit else (credit, "credit")
                else:
                    signed_amount = _parse_money_signed(amount_raw)
                    txn_type = declared_direction
                    if txn_type is None and signed_amount < 0:
                        txn_type = "debit"
                    if txn_type is None:
                        txn_type = _infer_direction(description)
                    if txn_type is None:
                        raise ValueError("transaction direction is ambiguous; add a type or debit/credit column")
                    amount = abs(signed_amount)

                if declared_direction and columns["amount"] and not (columns["debit"] or columns["credit"]):
                    txn_type = declared_direction
                explicit_currency = _get(row, columns["currency"]).upper() or "INR"
                if not re.fullmatch(r"[A-Z]{3}", explicit_currency):
                    raise ValueError(f"invalid currency code '{explicit_currency}'")
                explicit_merchant = _get(row, columns["merchant"])
                normalized_merchant = normalize_merchant(explicit_merchant) if explicit_merchant else normalize_merchant(description)
                raw_text = json.dumps({str(k): v for k, v in row.items()}, ensure_ascii=False, sort_keys=True)
                external_reference = _get(row, columns["external_reference"]) or None
                parsed.append((row_number, ParsedCsvTransaction(
                    txn_date, description, normalized_merchant, amount, txn_type, explicit_currency, raw_text,
                    external_reference,
                )))
            except ValueError as exc:
                errors.append(RowError(row_number, str(exc), json.dumps({str(k): v for k, v in row.items()}, ensure_ascii=False, sort_keys=True)))
    except csv.Error as exc:
        raise CsvFormatError(f"Could not read CSV rows: {exc}") from exc
    return parsed, errors


def _parse_money_signed(value: str) -> Decimal:
    candidate = value.strip().replace("₹", "").replace("INR", "").replace("inr", "").replace("Rs.", "").replace("Rs", "")
    candidate = candidate.replace(",", "").replace(" ", "")
    if not candidate:
        raise ValueError("amount is missing")
    negative = candidate.startswith("(") and candidate.endswith(")")
    if negative:
        candidate = candidate[1:-1]
    try:
        amount = Decimal(candidate)
    except InvalidOperation as exc:
        raise ValueError(f"invalid amount '{value}'") from exc
    if not amount.is_finite():
        raise ValueError(f"invalid amount '{value}' (must be finite)")
    if amount == 0:
        raise ValueError("amount must be non-zero")
    if abs(amount.as_tuple().exponent) > 2:
        raise ValueError("amount must have no more than two decimal places")
    if negative:
        amount = -amount
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
