from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_format: Mapped[str] = mapped_column(String(10), index=True)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    probable_duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    review_required_count: Mapped[int] = mapped_column(Integer, default=0)
    ignored_count: Mapped[int] = mapped_column(Integer, default=0)
    balance_reconciliation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transaction_reference", "external_reference"),
        Index("ix_transaction_fingerprint", "duplicate_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    transaction_date: Mapped[date] = mapped_column(Date, index=True)
    raw_narration: Mapped[str] = mapped_column(Text)
    cleaned_description: Mapped[str] = mapped_column(Text)
    normalized_merchant: Mapped[str | None] = mapped_column(String(180), nullable=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    transaction_type: Mapped[str] = mapped_column(String(10), index=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(80), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float)
    category_explanation: Mapped[str] = mapped_column(Text)
    source_format: Mapped[str] = mapped_column(String(10))
    duplicate_status: Mapped[str] = mapped_column(String(24), default="none", index=True)
    duplicate_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    external_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    original_raw_transaction_text: Mapped[str] = mapped_column(Text)
    import_batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), index=True)
    user_locked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ImportRow(Base):
    __tablename__ = "import_rows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_source_text: Mapped[str] = mapped_column(Text)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True)


class LearnedCategoryRule(Base):
    __tablename__ = "learned_category_rules"
    __table_args__ = (UniqueConstraint("merchant_key", name="uq_learned_rule_merchant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    merchant_key: Mapped[str] = mapped_column(String(180), index=True)
    category: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
