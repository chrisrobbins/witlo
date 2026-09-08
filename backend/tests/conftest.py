"""Test configuration for the tests that need a database or the HTTP app.

Environment variables are set *before* any app module is imported, because
`app.core.config.get_settings` is cached and `app.db.session` builds its engine
at import time. Getting this order wrong silently gives you a suite running
against whatever `.env` happens to be on the machine.

Every test here runs against a throwaway SQLite file with the mock providers.
Nothing in this suite can reach Stripe, PostGrid, or the postal service.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="wittl-tests-"))

os.environ.update(
    {
        "APP_MODE": "demo",
        "DATABASE_URL": f"sqlite+pysqlite:///{_TMP / 'test.db'}",
        "ADDRESS_PEPPER": "test-pepper-not-a-secret",
        "MAIL_PROVIDER": "mock",
        "PAYMENT_PROVIDER": "mock",
        "CORS_ALLOW_ORIGINS": "http://localhost:5173",
        "PRICE_POSTAGE_CENTS": "174",
        "PRICE_PRINTING_CENTS": "95",
        "PRICE_SERVICE_CENTS": "80",
        "REPEAT_ADDRESS_COOLDOWN_DAYS": "180",
        "MAX_LETTERS_PER_ADDRESS_LIFETIME": "3",
        "RATE_LIMIT_PER_IP_PER_HOUR": "1000",
        "RATE_LIMIT_DRAFTS_PER_IP_PER_DAY": "1000",
        "RETENTION_DAYS": "90",
        "TURNSTILE_SECRET_KEY": "",
        "RETURN_NAME": "Why Is This Light On?",
        "RETURN_LINE1": "PO Drawer 1",
        "RETURN_CITY": "Marfa",
        "RETURN_STATE": "TX",
        "RETURN_ZIP": "79843",
    }
)

from app.core.config import get_settings  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.providers.factory import get_providers  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_database() -> Iterator[None]:
    """A clean schema per test. These suites are small; isolation is worth more
    than the milliseconds a shared database would save."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db() -> Iterator:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def providers():
    return get_providers()


@pytest.fixture
def client() -> Iterator:
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
