from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

import pdfplumber

from parsers.csv_importer import CsvFormatError, ParsedCsvTransaction, RowError, _header_key, _parse_money_signed, parse_csv_bytes

SUPPORTED_LAYOUT = (
    "Supported PDF layout: machine-generated transaction table with Date, Narration/Description, "
    "and Debit/Credit columns (or Amount plus Type/Direction); optional Reference and Balance columns."
)


class PdfImportError(ValueError):
    pass


class ScannedPdfError(PdfImportError):
    pass


@dataclass(frozen=True)
class PdfParseResult:
    records: list[tuple[int, ParsedCsvTransaction]]
    errors: list[RowError]
    warnings: list[str]
    balance_reconciliation: dict | None
    total_rows: int


def _header_index(headers: list[str], options: tuple[str, ...]) -> int | None:
    normalized = [_header_key(header or "") for header in headers]
    for option in options:
        key = _header_key(option)
        if key in normalized:
            return normalized.index(key)
    return None


def _is_supported_header(headers: list[str]) -> bool:
    date_col = _header_index(headers, ("Date", "Transaction Date", "Txn Date", "Value Date"))
    desc_col = _header_index(headers, ("Narration", "Description", "Particulars", "Details"))
    debit_col = _header_index(headers, ("Debit", "Debit Amount", "Withdrawal"))
    credit_col = _header_index(headers, ("Credit", "Credit Amount", "Deposit"))
    amount_col = _header_index(headers, ("Amount", "Transaction Amount"))
    direction_col = _header_index(headers, ("Type", "Transaction Type", "Direction", "Dr/Cr"))
    return date_col is not None and desc_col is not None and (
        (debit_col is not None and credit_col is not None) or (amount_col is not None and direction_col is not None)
    )


def parse_pdf(content: bytes) -> PdfParseResult:
    if not content.startswith(b"%PDF"):
        raise PdfImportError("Uploaded file is not a PDF.")
    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:
        raise PdfImportError("Could not open this PDF. It may be encrypted or malformed.") from exc

    records: list[tuple[int, ParsedCsvTransaction]] = []
    errors: list[RowError] = []
    warnings: list[str] = []
    balance_values: list[Decimal | None] = []
    total_rows = 0
    any_text = False
    try:
        for page_number, page in enumerate(pdf.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                any_text = True
            else:
                warnings.append(f"Page {page_number} contains no extractable text; it may be scanned.")
                continue
            supported_table_found = False
            for table in page.extract_tables() or []:
                if not table or not table[0]:
                    continue
                headers = [str(value or "").replace("\n", " ").strip() for value in table[0]]
                if not _is_supported_header(headers):
                    if len(table) > 1:
                        warnings.append(f"Page {page_number} contains an unsupported table; it was not imported.")
                    continue
                supported_table_found = True
                balance_index = _header_index(headers, ("Balance", "Closing Balance", "Running Balance"))
                external_index = _header_index(headers, ("Reference", "Ref No", "UTR", "RRN", "Transaction ID"))
                writer_buffer = io.StringIO()
                writer = csv.writer(writer_buffer)
                writer.writerow(headers)
                usable_rows = []
                for row in table[1:]:
                    if not row or not any(str(value or "").strip() for value in row):
                        continue
                    values = [str(value or "").replace("\n", " ").strip() for value in row]
                    if len(values) < len(headers):
                        values.extend([""] * (len(headers) - len(values)))
                    usable_rows.append(values)
                    writer.writerow(values)
                parsed, row_errors = parse_csv_bytes(writer_buffer.getvalue().encode("utf-8-sig"))
                offset = total_rows
                total_rows += len(usable_rows)
                for parsed_row, item in parsed:
                    global_row = offset + parsed_row - 1
                    source_row = usable_rows[parsed_row - 2]
                    raw_text = json.dumps(
                        {"page": page_number, "cells": source_row, "narration": item.description},
                        ensure_ascii=False,
                    )
                    reference = source_row[external_index] if external_index is not None else item.external_reference
                    records.append((global_row, ParsedCsvTransaction(
                        item.transaction_date, item.description, item.normalized_merchant, item.amount,
                        item.transaction_type, item.currency, raw_text, reference or None,
                    )))
                    if balance_index is None:
                        balance_values.append(None)
                    else:
                        balance_raw = source_row[balance_index]
                        try:
                            balance_values.append(_parse_money_signed(balance_raw) if balance_raw else None)
                        except ValueError:
                            balance_values.append(None)
                            warnings.append(f"Page {page_number}, row {parsed_row}: balance value could not be parsed.")
                for row_error in row_errors:
                    global_row = offset + row_error.row_number - 1
                    errors.append(RowError(global_row, f"page {page_number}: {row_error.error}", row_error.raw_text))
            if not supported_table_found:
                warnings.append(f"Page {page_number} has text but no table matching the supported layout.")
    finally:
        pdf.close()

    if not any_text:
        raise ScannedPdfError("PDF contains no extractable text and appears scanned. OCR is not supported.")
    if not records and not errors:
        raise PdfImportError(SUPPORTED_LAYOUT)

    balance_info = _reconcile(records, balance_values)
    if balance_info and balance_info.get("status") == "mismatch":
        warnings.append("Running balance did not reconcile for every checked row; inspect the batch details.")
    return PdfParseResult(records, errors, warnings, balance_info, total_rows)


def _reconcile(records: list[tuple[int, ParsedCsvTransaction]], balances: list[Decimal | None]) -> dict | None:
    if not balances or all(value is None for value in balances):
        return {"status": "not_available", "checked_rows": 0, "discrepancies": []}
    indexed = [(record[0], record[1], balances[index]) for index, record in enumerate(records) if index < len(balances)]
    indexed = [item for item in indexed if item[2] is not None]
    indexed.sort(key=lambda item: (item[1].transaction_date, item[0]))
    if len(indexed) < 2:
        return {"status": "insufficient_data", "checked_rows": 0, "discrepancies": []}
    discrepancies = []
    checked = 0
    for previous, current in zip(indexed, indexed[1:]):
        previous_balance = previous[2]
        current_balance = current[2]
        expected_change = current[1].amount if current[1].transaction_type == "credit" else -current[1].amount
        actual_change = current_balance - previous_balance
        checked += 1
        if abs(actual_change - expected_change) > Decimal("0.01"):
            discrepancies.append({
                "row_number": current[0],
                "expected_change": str(expected_change),
                "observed_change": str(actual_change),
            })
    return {"status": "reconciled" if not discrepancies else "mismatch", "checked_rows": checked, "discrepancies": discrepancies}
