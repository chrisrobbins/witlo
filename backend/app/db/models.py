"""Database schema.

Three tables carry the safety properties, and each does it with a unique
constraint rather than with application logic:

  * `webhook_events(provider, event_id)` — a replayed webhook is a primary key
    collision, so a duplicate "you were paid" cannot be processed twice even if
    two workers receive it simultaneously.
  * `idempotency_keys(scope, key)` — a retried checkout returns the stored
    response instead of opening a second session.
  * `letters.provider_letter_id` — unique, so two submissions can never both
    record a letter at the printer.

Retention: `purge_after` is set when a letter reaches a final state, and the
retention job blanks the recipient address, the letter text and the sender's
email while keeping the address hash and the outcome. What remains is enough to
honour a cooldown and a do-not-mail request and not enough to reconstruct the
letter.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:24]}"


class Base(DeclarativeBase):
    pass


class Letter(Base):
    __tablename__ = "letters"

    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: new_id("ltr"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    status_detail: Mapped[str] = mapped_column(Text, default="")

    # --- recipient (cleared at retention) ---------------------------------
    to_line1: Mapped[str] = mapped_column(String(120), default="")
    to_line2: Mapped[str] = mapped_column(String(80), default="")
    to_city: Mapped[str] = mapped_column(String(80), default="")
    to_state: Mapped[str] = mapped_column(String(2), default="")
    to_zip: Mapped[str] = mapped_column(String(10), default="")
    #: HMAC of the normalized address. Survives retention; drives cooldown.
    address_hash: Mapped[str] = mapped_column(String(64), index=True)

    # --- content ----------------------------------------------------------
    observations: Mapped[list] = mapped_column(JSON, default=list)
    suggestions: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default="")
    letter_text: Mapped[str] = mapped_column(Text, default="")
    letter_fingerprint: Mapped[str] = mapped_column(String(16), default="")
    content_version: Mapped[str] = mapped_column(String(16), default="")
    pages: Mapped[int] = mapped_column(Integer, default=1)

    # --- sender (minimal; never printed on the letter) --------------------
    sender_email: Mapped[str] = mapped_column(String(254), default="")
    client_hash: Mapped[str] = mapped_column(String(64), default="", index=True)

    # --- money ------------------------------------------------------------
    currency: Mapped[str] = mapped_column(String(8), default="usd")
    quoted_cents: Mapped[int] = mapped_column(Integer, default=0)
    amount_paid_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payment_provider: Mapped[str] = mapped_column(String(24), default="")
    payment_session_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- mailing ----------------------------------------------------------
    mail_provider: Mapped[str] = mapped_column(String(24), default="")
    provider_letter_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expected_delivery_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    submit_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")

    # --- retention --------------------------------------------------------
    purge_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    purged: Mapped[bool] = mapped_column(Boolean, default=False)

    events: Mapped[list[LetterEvent]] = relationship(
        back_populates="letter", cascade="all, delete-orphan", order_by="LetterEvent.created_at"
    )

    __table_args__ = (
        # One row at the printer per letter, enforced by the database.
        UniqueConstraint("provider_letter_id", name="uq_letters_provider_letter_id"),
        Index("ix_letters_address_hash_status", "address_hash", "status"),
        Index("ix_letters_created_at", "created_at"),
    )


class LetterEvent(Base):
    """An append-only history. Nothing here is ever updated or deleted."""

    __tablename__ = "letter_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    letter_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("letters.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    from_status: Mapped[str] = mapped_column(String(32), default="")
    to_status: Mapped[str] = mapped_column(String(32), default="")
    source: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")

    letter: Mapped[Letter] = relationship(back_populates="events")


class WebhookEvent(Base):
    """Every webhook we accept, recorded before it is acted on.

    The unique constraint is the duplicate-event defence: a replay collides,
    the insert fails, and the handler returns 200 without doing the work twice.
    """

    __tablename__ = "webhook_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(24))
    event_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(80), default="")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    letter_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    #: Digest only. Webhook bodies contain recipient addresses.
    body_digest: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (
        UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )


class IdempotencyKey(Base):
    """Client-supplied keys for operations that must not run twice."""

    __tablename__ = "idempotency_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(40))
    key: Mapped[str] = mapped_column(String(120))
    letter_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    response_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),)


class Suppression(Base):
    """The do-not-mail list. Stored as a hash; there is no way back to an address."""

    __tablename__ = "suppressions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    address_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source: Mapped[str] = mapped_column(String(32), default="web")
    note: Mapped[str] = mapped_column(Text, default="")


class RateLimitBucket(Base):
    """Fixed-window counters, in the database so limits survive a restart and
    hold across more than one instance."""

    __tablename__ = "rate_limit_buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bucket: Mapped[str] = mapped_column(String(160))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("bucket", "window_start", name="uq_rate_limit_bucket_window"),
    )
