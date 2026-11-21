from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from models import Base  # noqa: E402
from transaction_db import get_db  # noqa: E402
from transaction_main import app  # noqa: E402


@pytest.fixture
def test_database():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestingSession
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(test_database):
    session = test_database()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_database):
    # Avoid the app's production DB lifespan; routes use the test DB dependency override.
    return TestClient(app)
