"""Fixed-window rate limiting, backed by the database.

In the database rather than in memory so the limit survives a restart and holds
across more than one instance — an in-process counter on a platform that runs
two containers is a limit of 2N that nobody notices until it matters.

Keys are peppered hashes of the client IP; nothing here stores an address.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import RateLimitBucket


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp(epoch - (epoch % window_seconds), tz=UTC)


def check_and_consume(
    db: Session,
    bucket: str,
    limit: int,
    window_seconds: int,
    *,
    now: datetime | None = None,
) -> RateLimitResult:
    """Increment the counter for `bucket` and say whether the call may proceed."""
    if limit <= 0:
        return RateLimitResult(allowed=True, remaining=0, retry_after_seconds=0)

    current = now or datetime.now(UTC)
    start = _window_start(current, window_seconds)

    row = db.execute(
        select(RateLimitBucket).where(
            RateLimitBucket.bucket == bucket, RateLimitBucket.window_start == start
        )
    ).scalar_one_or_none()

    if row is None:
        row = RateLimitBucket(bucket=bucket, window_start=start, count=0)
        db.add(row)
        try:
            db.flush()
        except IntegrityError:
            # Another worker created the same window first; use theirs.
            db.rollback()
            row = db.execute(
                select(RateLimitBucket).where(
                    RateLimitBucket.bucket == bucket, RateLimitBucket.window_start == start
                )
            ).scalar_one()

    retry_after = int((start + timedelta(seconds=window_seconds) - current).total_seconds())

    if row.count >= limit:
        return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(retry_after, 1))

    row.count += 1
    db.flush()
    return RateLimitResult(
        allowed=True, remaining=max(limit - row.count, 0), retry_after_seconds=retry_after
    )


def purge_old_buckets(db: Session, older_than_days: int = 2) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
    rows = db.execute(
        select(RateLimitBucket).where(RateLimitBucket.window_start < cutoff)
    ).scalars()
    count = 0
    for row in rows:
        db.delete(row)
        count += 1
    return count
