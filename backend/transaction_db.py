from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from models import Base

# Isolate the new integer-paise schema from any pre-existing application database.
DEFAULT_DB = Path(__file__).resolve().with_name("transaction_intelligence.db")
DATABASE_URL = os.getenv("ARTHATWIN_TRANSACTIONS_DATABASE_URL", f"sqlite:///{DEFAULT_DB}")
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
