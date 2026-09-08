"""Engine and session management.

PostgreSQL in production; SQLite is supported so a contributor can run the API
with no services installed. The SQLite branch turns on WAL and foreign keys,
because the default settings do not behave like the database this app is
actually deployed on and quiet differences are the worst kind.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()

_connect_args: dict = {}
_engine_kwargs: dict = {"pool_pre_ping": True, "future": True}
if _settings.database_url.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
else:
    # Serverless (Vercel) freezes the process between requests, so a held
    # connection pool goes stale; let Postgres — or Neon's pooler — own pooling
    # and open a fresh connection per invocation.
    _engine_kwargs["poolclass"] = NullPool

engine: Engine = create_engine(
    _settings.database_url,
    connect_args=_connect_args,
    **_engine_kwargs,
)

if _settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver glue
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """For background work and scripts."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
