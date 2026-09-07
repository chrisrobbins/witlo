"""Rate limiting.

Database-backed so the limit survives a restart and holds across instances;
these tests check the window arithmetic and that the counter is actually shared
rather than per-process.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.ratelimit import check_and_consume, purge_old_buckets
from app.db.session import SessionLocal

NOW = datetime(2026, 9, 7, 12, 30, 45, tzinfo=UTC)


def test_a_bucket_allows_exactly_its_limit(db) -> None:
    for index in range(3):
        result = check_and_consume(db, "test", 3, 3600, now=NOW)
        assert result.allowed is True, index
    assert check_and_consume(db, "test", 3, 3600, now=NOW).allowed is False


def test_a_blocked_caller_is_told_when_to_come_back(db) -> None:
    for _ in range(2):
        check_and_consume(db, "test", 2, 3600, now=NOW)
    blocked = check_and_consume(db, "test", 2, 3600, now=NOW)
    assert blocked.allowed is False
    assert 0 < blocked.retry_after_seconds <= 3600


def test_the_next_window_starts_fresh(db) -> None:
    for _ in range(2):
        check_and_consume(db, "test", 2, 3600, now=NOW)
    assert check_and_consume(db, "test", 2, 3600, now=NOW).allowed is False
    assert check_and_consume(db, "test", 2, 3600, now=NOW + timedelta(hours=1)).allowed is True


def test_buckets_do_not_interfere_with_each_other(db) -> None:
    for _ in range(2):
        check_and_consume(db, "a", 2, 3600, now=NOW)
    assert check_and_consume(db, "a", 2, 3600, now=NOW).allowed is False
    assert check_and_consume(db, "b", 2, 3600, now=NOW).allowed is True


def test_the_counter_is_shared_between_sessions(db) -> None:
    """Two workers must see one counter, not one each."""
    check_and_consume(db, "shared", 2, 3600, now=NOW)
    db.commit()

    with SessionLocal() as other:
        check_and_consume(other, "shared", 2, 3600, now=NOW)
        other.commit()

    assert check_and_consume(db, "shared", 2, 3600, now=NOW).allowed is False


def test_a_limit_of_zero_disables_the_check_rather_than_blocking_everything(db) -> None:
    assert check_and_consume(db, "off", 0, 3600, now=NOW).allowed is True


def test_old_windows_can_be_swept_up(db) -> None:
    check_and_consume(db, "old", 5, 3600, now=NOW - timedelta(days=10))
    check_and_consume(db, "new", 5, 3600, now=datetime.now(UTC))
    db.commit()
    assert purge_old_buckets(db, older_than_days=2) == 1
