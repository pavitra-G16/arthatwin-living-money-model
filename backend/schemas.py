from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from transaction_engine.categorizer import CATEGORIES

UserCategory = Literal[
    "Food & Dining", "Groceries", "Transport", "Shopping", "Bills & Utilities",
    "Subscriptions", "Healthcare", "Education", "Rent", "Salary / Income",
    "Transfers", "Cash Withdrawal", "Other",
]


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    transaction_date: date
    raw_narration: str
    cleaned_description: str
    normalized_merchant: str | None
    amount_paise: int
    currency: str
    transaction_type: str
    category: str
    subcategory: str | None
    confidence_score: float
    category_explanation: str
    source_format: str
    duplicate_status: str
    external_reference: str | None
    import_batch_id: str
    user_locked: bool


class RowIssue(BaseModel):
    row_number: int
    status: str
    message: str | None
    raw_source_text: str


class ImportBatchSummary(BaseModel):
    batch_id: str
    source_format: str
    source_name: str | None
    total_rows: int
    imported_count: int
    rejected_count: int
    duplicate_count: int
    probable_duplicate_count: int
    review_required_count: int
    ignored_count: int
    balance_reconciliation: dict | None
    warnings: list[str]
    rows: list[RowIssue] = Field(default_factory=list)


class TransactionPage(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[TransactionRead]


class SmsParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class SmsParseResponse(BaseModel):
    raw_text: str
    transaction_date: date | None
    description: str
    normalized_merchant: str | None
    amount_paise: int | None
    transaction_type: str | None
    category: str
    confidence_score: float
    category_explanation: str
    missing_fields: list[str]
    needs_review: bool
    ignored_reason: str | None
    external_reference: str | None


class SmsImportRequest(BaseModel):
    messages: list[str] = Field(min_length=1, max_length=500)

    @field_validator("messages")
    @classmethod
    def messages_nonempty(cls, value: list[str]) -> list[str]:
        if any(not message.strip() for message in value):
            raise ValueError("SMS messages cannot be blank")
        return value


class CategoryCorrection(BaseModel):
    category: UserCategory
    apply_to_matching: bool = False


class CategoryCorrectionPreview(BaseModel):
    transaction_id: str
    merchant: str
    proposed_category: str
    eligible_count: int
    locked_count: int
    sample_transaction_ids: list[str]


class CategoryCorrectionResult(BaseModel):
    transaction_id: str
    merchant: str
    category: str
    rule_id: str
    rule_created: bool
    rule_applied_to_existing_count: int
    locked_transactions_skipped: int
    updated_transaction_ids: list[str]
    message: str


class LearnedRuleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    merchant_key: str
    category: str
    created_at: datetime
    updated_at: datetime


class HealthRead(BaseModel):
    status: str
    database: str
