"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-07

The unique constraints created here are load-bearing, not hygiene:
  * uq_webhook_events_provider_event  — a replayed webhook cannot be processed twice
  * uq_idempotency_scope_key          — a retried checkout cannot charge twice
  * uq_letters_provider_letter_id     — a retried submission cannot mail twice
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "letters",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("status_detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("to_line1", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("to_line2", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("to_city", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("to_state", sa.String(length=2), nullable=False, server_default=""),
        sa.Column("to_zip", sa.String(length=10), nullable=False, server_default=""),
        sa.Column("address_hash", sa.String(length=64), nullable=False),
        sa.Column("observations", sa.JSON(), nullable=False),
        sa.Column("suggestions", sa.JSON(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("letter_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("letter_fingerprint", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("content_version", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sender_email", sa.String(length=254), nullable=False, server_default=""),
        sa.Column("client_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="usd"),
        sa.Column("quoted_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("amount_paid_cents", sa.Integer(), nullable=True),
        sa.Column("payment_provider", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("payment_session_id", sa.String(length=120), nullable=True),
        sa.Column("payment_reference", sa.String(length=120), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("mail_provider", sa.String(length=24), nullable=False, server_default=""),
        sa.Column("provider_letter_id", sa.String(length=120), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_delivery_date", sa.String(length=10), nullable=True),
        sa.Column("submit_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purged", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("provider_letter_id", name="uq_letters_provider_letter_id"),
    )
    op.create_index("ix_letters_status", "letters", ["status"])
    op.create_index("ix_letters_address_hash", "letters", ["address_hash"])
    op.create_index("ix_letters_address_hash_status", "letters", ["address_hash", "status"])
    op.create_index("ix_letters_created_at", "letters", ["created_at"])
    op.create_index("ix_letters_client_hash", "letters", ["client_hash"])
    op.create_index("ix_letters_purge_after", "letters", ["purge_after"])
    op.create_index("ix_letters_payment_session_id", "letters", ["payment_session_id"])

    op.create_table(
        "letter_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "letter_id",
            sa.String(length=40),
            sa.ForeignKey("letters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("from_status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("to_status", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=""),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_letter_events_letter_id", "letter_events", ["letter_id"])

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("event_id", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("letter_id", sa.String(length=40), nullable=True),
        sa.Column("body_digest", sa.String(length=64), nullable=False, server_default=""),
        sa.UniqueConstraint("provider", "event_id", name="uq_webhook_events_provider_event"),
    )
    op.create_index("ix_webhook_events_letter_id", "webhook_events", ["letter_id"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(length=40), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("letter_id", sa.String(length=40), nullable=True),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )

    op.create_table(
        "suppressions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("address_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_suppressions_address_hash", "suppressions", ["address_hash"])

    op.create_table(
        "rate_limit_buckets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bucket", sa.String(length=160), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("bucket", "window_start", name="uq_rate_limit_bucket_window"),
    )


def downgrade() -> None:
    op.drop_table("rate_limit_buckets")
    op.drop_index("ix_suppressions_address_hash", table_name="suppressions")
    op.drop_table("suppressions")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_webhook_events_letter_id", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_letter_events_letter_id", table_name="letter_events")
    op.drop_table("letter_events")
    for name in (
        "ix_letters_payment_session_id",
        "ix_letters_purge_after",
        "ix_letters_client_hash",
        "ix_letters_created_at",
        "ix_letters_address_hash_status",
        "ix_letters_address_hash",
        "ix_letters_status",
    ):
        op.drop_index(name, table_name="letters")
    op.drop_table("letters")
