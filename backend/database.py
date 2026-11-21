import os
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, Numeric, Text, Index, text
from sqlalchemy.orm import declarative_base, sessionmaker

def normalize_database_url(value: str) -> str:
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://"):]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL", "sqlite:///./arthatwin.db"))

engine_options = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)
    raw_narration = Column(String)
    merchant = Column(String, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    txn_type = Column(String, default="DEBIT")
    category = Column(String, index=True)
    source = Column(String)
    confidence_source = Column(String, default="RULE_ENGINE")
    user_locked = Column(Boolean, default=False)
    security_flag = Column(String, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurring_alert = Column(String, nullable=True)
    fingerprint = Column(String, nullable=True)
    is_demo = Column(Boolean, nullable=False, default=False)
    confidence_score = Column(Float, nullable=False, default=0.0)


class LearnedRule(Base):
    __tablename__ = "learned_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, unique=True, index=True)
    category = Column(String)
    explanation = Column(String)
    hit_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_enabled = Column(Boolean, nullable=False, default=True)
    is_demo = Column(Boolean, nullable=False, default=False)


class SubscriptionFeedback(Base):
    __tablename__ = "subscription_feedback"

    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String, unique=True, index=True)
    still_uses = Column(String, default="unsure")  # yes, no, unsure
    is_demo = Column(Boolean, nullable=False, default=False)


class FinancialProfile(Base):
    __tablename__ = "financial_profile"

    id = Column(Integer, primary_key=True, index=True)
    monthly_income = Column(Numeric(14, 2), default=0)
    fixed_costs = Column(Numeric(14, 2), default=0)
    emergency_fund_current = Column(Numeric(14, 2), default=0)
    emergency_fund_target = Column(Numeric(14, 2), default=0)
    discretionary_budget = Column(Numeric(14, 2), default=0)
    is_demo = Column(Boolean, nullable=False, default=False)


class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    target_amount = Column(Numeric(14, 2))
    saved_amount = Column(Numeric(14, 2))
    target_date = Column(String)
    priority = Column(Integer, default=1)
    is_demo = Column(Boolean, nullable=False, default=False)


class ImportPreview(Base):
    __tablename__ = "import_previews"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    filename = Column(String, nullable=True)
    payload_json = Column(Text, nullable=False)
    issues_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class MonthCoverage(Base):
    __tablename__ = "month_coverage"

    id = Column(Integer, primary_key=True)
    month = Column(String, nullable=False, index=True)
    confirmed_complete = Column(Boolean, nullable=False, default=False)
    is_demo = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as connection:
            columns = {row[1] for row in connection.execute(text("PRAGMA table_info(transactions)"))}
            migrations = {
                "fingerprint": "ALTER TABLE transactions ADD COLUMN fingerprint VARCHAR",
                "is_demo": "ALTER TABLE transactions ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0",
                "confidence_score": "ALTER TABLE transactions ADD COLUMN confidence_score FLOAT NOT NULL DEFAULT 0",
            }
            for name, statement in migrations.items():
                if name not in columns:
                    connection.execute(text(statement))
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_fingerprint ON transactions (fingerprint)"))
            rule_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(learned_rules)"))}
            if "is_enabled" not in rule_columns:
                connection.execute(text("ALTER TABLE learned_rules ADD COLUMN is_enabled BOOLEAN NOT NULL DEFAULT 1"))
            if "is_demo" not in rule_columns:
                connection.execute(text("ALTER TABLE learned_rules ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0"))
            goal_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(financial_goals)"))}
            if "is_demo" not in goal_columns:
                connection.execute(text("ALTER TABLE financial_goals ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0"))
            profile_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(financial_profile)"))}
            if "is_demo" not in profile_columns:
                connection.execute(text("ALTER TABLE financial_profile ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0"))
            feedback_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(subscription_feedback)"))}
            if "is_demo" not in feedback_columns:
                connection.execute(text("ALTER TABLE subscription_feedback ADD COLUMN is_demo BOOLEAN NOT NULL DEFAULT 0"))
    elif engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_transactions_fingerprint ON transactions (fingerprint)"))
