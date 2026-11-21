from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./arthatwin.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String, index=True)
    raw_narration = Column(String)
    merchant = Column(String, index=True)
    amount = Column(Float)
    txn_type = Column(String, default="DEBIT")
    category = Column(String, index=True)
    source = Column(String)
    confidence_source = Column(String, default="RULE_ENGINE")
    user_locked = Column(Boolean, default=False)
    security_flag = Column(String, nullable=True)
    is_recurring = Column(Boolean, default=False)
    recurring_alert = Column(String, nullable=True)


class LearnedRule(Base):
    __tablename__ = "learned_rules"

    id = Column(Integer, primary_key=True, index=True)
    pattern = Column(String, unique=True, index=True)
    category = Column(String)
    explanation = Column(String)
    hit_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class SubscriptionFeedback(Base):
    __tablename__ = "subscription_feedback"

    id = Column(Integer, primary_key=True, index=True)
    merchant = Column(String, unique=True, index=True)
    still_uses = Column(String, default="unsure")  # yes, no, unsure


class FinancialProfile(Base):
    __tablename__ = "financial_profile"

    id = Column(Integer, primary_key=True, index=True)
    monthly_income = Column(Float, default=85000.0)
    fixed_costs = Column(Float, default=32000.0)
    emergency_fund_current = Column(Float, default=95000.0)
    emergency_fund_target = Column(Float, default=250000.0)
    discretionary_budget = Column(Float, default=25000.0)


class FinancialGoal(Base):
    __tablename__ = "financial_goals"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    target_amount = Column(Float)
    saved_amount = Column(Float)
    target_date = Column(String)
    priority = Column(Integer, default=1)


def init_db():
    Base.metadata.create_all(bind=engine)
