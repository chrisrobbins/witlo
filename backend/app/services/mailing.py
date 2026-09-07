"""Orchestration: drafts, checkout, payment webhooks, submission, retries.

The invariants this module exists to hold:

1. A letter is printed only from `paid`, and only through `submit_letter`,
   which moves it to `submitting` in its own committed transaction first. A
   crash after that leaves a letter stuck in `submitting`, which the retry job
   can inspect — far better than a crash that leaves it in `paid` and gets
   submitted twice.
2. The provider call carries the letter id as its idempotency key, so even a
   double submission produces one envelope.
3. `provider_letter_id` is unique in the database, so if the provider ever did
   return two ids for one letter, the second write fails loudly.
4. Only a verified webhook can move a letter to `paid`.
5. A letter that was paid for and cannot be mailed is refunded, not retried
   forever.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import digest
from app.db.models import IdempotencyKey, Letter, LetterEvent, Suppression, WebhookEvent, utcnow
from app.letters.address import UsAddress, address_hash
from app.letters.composer import (
    LetterInput,
    compose_letter,
    letter_fingerprint,
    today_iso,
)
from app.letters.render import render_letter_html
from app.payments.base import (
    CheckoutRequest,
    PaymentError,
    PaymentEvent,
    PaymentEventKind,
    PaymentProvider,
)
from app.providers.base import (
    MailProvider,
    MailProviderError,
    ProviderEvent,
    SendLetterRequest,
)
from app.services.pricing import Quote, build_quote, estimate_pages
from app.services.state import (
    COUNTS_TOWARD_COOLDOWN,
    PROVIDER_EVENT_STATUS,
    InvalidTransition,
    LetterStatus,
    assert_transition,
    is_chargeable,
    is_mailable,
)

log = logging.getLogger(__name__)

MAX_SUBMIT_ATTEMPTS = 4


class ServiceError(Exception):
    """An error with a message that is safe to show a sender."""

    def __init__(self, message: str, *, code: str = "error", status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


# --------------------------------------------------------------------------
# state transitions
# --------------------------------------------------------------------------


def move(
    db: Session, letter: Letter, target: LetterStatus, *, source: str, detail: str = ""
) -> None:
    """The only way a letter's status changes."""
    current = LetterStatus(letter.status)
    assert_transition(current, target)
    if current == target and not detail:
        return
    letter.status = target.value
    if detail:
        letter.status_detail = detail
    db.add(
        LetterEvent(
            letter_id=letter.id,
            from_status=current.value,
            to_status=target.value,
            source=source,
            detail=detail[:2000],
        )
    )


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------


def is_suppressed(db: Session, hashed: str) -> bool:
    return (
        db.execute(select(Suppression.id).where(Suppression.address_hash == hashed)).first()
        is not None
    )


def add_suppression(db: Session, hashed: str, *, source: str, note: str = "") -> None:
    """Idempotent: asking twice is not an error, and must never 500."""
    if is_suppressed(db, hashed):
        return
    db.add(Suppression(address_hash=hashed, source=source, note=note[:500]))
    try:
        db.flush()
    except IntegrityError:
        db.rollback()


def cooldown_until(db: Session, hashed: str, settings: Settings) -> datetime | None:
    """When the next letter to this address may go out, or None if it may now."""
    if settings.repeat_address_cooldown_days <= 0:
        return None
    last = db.execute(
        select(func.max(Letter.created_at)).where(
            Letter.address_hash == hashed,
            Letter.status.in_([s.value for s in COUNTS_TOWARD_COOLDOWN]),
        )
    ).scalar()
    if last is None:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    ends = last + timedelta(days=settings.repeat_address_cooldown_days)
    return ends if ends > datetime.now(timezone.utc) else None


def lifetime_letters(db: Session, hashed: str) -> int:
    return int(
        db.execute(
            select(func.count(Letter.id)).where(
                Letter.address_hash == hashed,
                Letter.status.in_([s.value for s in COUNTS_TOWARD_COOLDOWN]),
            )
        ).scalar()
        or 0
    )


# --------------------------------------------------------------------------
# drafts
# --------------------------------------------------------------------------


def quote_for(settings: Settings, pages: int) -> Quote:
    return build_quote(
        postage_cents=settings.price_postage_cents,
        printing_cents=settings.price_printing_cents,
        service_cents=settings.price_service_cents,
        currency=settings.price_currency,
        pages=pages,
    )


def create_draft(
    db: Session,
    *,
    settings: Settings,
    address: UsAddress,
    observations: list[str],
    note: str,
    suggestions: list[str],
    client_fingerprint: str | None,
    sender_email: str,
    client_hash: str,
) -> tuple[Letter, Quote]:
    """Compose the letter server-side and store it.

    The client's fingerprint is compared against the server's own composition.
    A mismatch means the browser is describing a different letter from the one
    this code would print, and the only safe response is to refuse.
    """
    hashed = address_hash(address, settings.address_pepper)

    if is_suppressed(db, hashed):
        raise ServiceError(
            "This address has asked not to receive letters from this service.",
            code="suppressed",
            status_code=409,
        )

    ends = cooldown_until(db, hashed, settings)
    if ends is not None:
        raise ServiceError(
            "A letter has gone to this address recently. The next one can go out on "
            f"{ends.date().isoformat()}.",
            code="cooldown",
            status_code=409,
        )

    if lifetime_letters(db, hashed) >= settings.max_letters_per_address_lifetime:
        raise ServiceError(
            "This address has received the maximum number of letters this service will send.",
            code="lifetime_limit",
            status_code=409,
        )

    doc = compose_letter(
        LetterInput(
            address=address,
            observations=observations,
            note=note,
            suggestions=suggestions,
            date_iso=today_iso(),
        )
    )
    server_fingerprint = letter_fingerprint(doc.plain_text)

    if client_fingerprint and client_fingerprint != server_fingerprint:
        raise ServiceError(
            "The letter shown in your browser does not match what we would print. "
            "Please reload and read it again before sending.",
            code="fingerprint_mismatch",
            status_code=409,
        )

    pages = estimate_pages(doc.plain_text)
    quote = quote_for(settings, pages)

    letter = Letter(
        status=LetterStatus.DRAFT.value,
        to_line1=address.line1,
        to_line2=address.line2,
        to_city=address.city,
        to_state=address.state,
        to_zip=address.zip,
        address_hash=hashed,
        observations=list(observations),
        suggestions=list(suggestions),
        note=note,
        letter_text=doc.plain_text,
        letter_fingerprint=server_fingerprint,
        content_version=doc.content_version,
        pages=pages,
        sender_email=sender_email,
        client_hash=client_hash,
        currency=quote.currency,
        quoted_cents=quote.total_cents,
        mail_provider=settings.mail_provider,
        payment_provider=settings.payment_provider,
    )
    db.add(letter)
    db.flush()
    db.add(
        LetterEvent(letter_id=letter.id, from_status="", to_status="draft", source="api")
    )
    return letter, quote


def recipient_address(letter: Letter) -> UsAddress:
    return UsAddress(
        line1=letter.to_line1,
        line2=letter.to_line2,
        city=letter.to_city,
        state=letter.to_state,
        zip=letter.to_zip,
    )


# --------------------------------------------------------------------------
# checkout
# --------------------------------------------------------------------------


def start_checkout(
    db: Session,
    *,
    settings: Settings,
    payments: PaymentProvider,
    letter: Letter,
    idempotency_key: str,
) -> dict:
    """Open a hosted checkout session, at most once per idempotency key."""
    if not is_chargeable(LetterStatus(letter.status)):
        raise ServiceError(
            "This letter is past the point where it can be paid for.",
            code="not_chargeable",
            status_code=409,
        )

    scope = "checkout"
    existing = db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.scope == scope, IdempotencyKey.key == idempotency_key
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.letter_id != letter.id:
            raise ServiceError(
                "That idempotency key was already used for a different letter.",
                code="idempotency_conflict",
                status_code=409,
            )
        return dict(existing.response_json)

    # Recompute rather than trusting the stored number, so an edited draft
    # cannot be paid for at yesterday's price.
    quote = quote_for(settings, letter.pages)
    if quote.total_cents != letter.quoted_cents:
        letter.quoted_cents = quote.total_cents
        letter.currency = quote.currency

    session = payments.create_checkout_session(
        CheckoutRequest(
            letter_id=letter.id,
            amount_cents=quote.total_cents,
            currency=quote.currency,
            description="One friendly letter about outdoor lighting, printed and posted",
            success_url=settings.checkout_success_url.replace("{LETTER_ID}", letter.id),
            cancel_url=settings.checkout_cancel_url,
            idempotency_key=idempotency_key,
            customer_email=letter.sender_email or None,
            metadata={"content_version": letter.content_version},
        )
    )

    letter.payment_provider = session.provider
    letter.payment_session_id = session.session_id
    move(db, letter, LetterStatus.PENDING_PAYMENT, source="checkout")

    response = {"checkoutUrl": session.url, "draftId": letter.id}
    db.add(
        IdempotencyKey(
            scope=scope, key=idempotency_key, letter_id=letter.id, response_json=response
        )
    )
    try:
        db.flush()
    except IntegrityError:
        # Two concurrent submissions of the same key: keep whichever landed.
        db.rollback()
        stored = db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.scope == scope, IdempotencyKey.key == idempotency_key
            )
        ).scalar_one()
        return dict(stored.response_json)

    return response


# --------------------------------------------------------------------------
# webhooks
# --------------------------------------------------------------------------


def record_webhook(
    db: Session, *, provider: str, event_id: str, event_type: str, body: bytes, letter_id: str | None
) -> bool:
    """Record the event. Returns False if it has already been seen.

    The uniqueness check is the database's, not a query-then-insert: two workers
    handed the same replayed event will both try to insert, and exactly one will
    succeed.
    """
    row = WebhookEvent(
        provider=provider,
        event_id=event_id or f"unsigned-{digest(body.decode('utf-8', 'replace'))[:32]}",
        event_type=event_type,
        letter_id=letter_id,
        body_digest=digest(body.decode("utf-8", "replace")),
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return False
    return True


def handle_payment_event(
    db: Session, *, settings: Settings, event: PaymentEvent
) -> Letter | None:
    """Apply a verified payment event. The only path to `paid`."""
    if event.kind is PaymentEventKind.IGNORED:
        return None
    if not event.letter_id:
        log.warning("payment event %s has no letter id", event.event_id)
        return None

    letter = db.get(Letter, event.letter_id)
    if letter is None:
        log.warning("payment event %s references an unknown letter", event.event_id)
        return None

    if not record_webhook(
        db,
        provider=event.provider,
        event_id=event.event_id,
        event_type=event.kind.value,
        body=b"",
        letter_id=letter.id,
    ):
        log.info("duplicate payment event %s ignored", event.event_id)
        return letter

    if event.kind is PaymentEventKind.PAID:
        if LetterStatus(letter.status) in {LetterStatus.PAID, LetterStatus.SUBMITTING} or \
                LetterStatus(letter.status) == LetterStatus.SUBMITTED:
            return letter  # already handled
        # Refuse a payment whose amount is not the amount we quoted.
        if event.amount_cents is not None and event.amount_cents != letter.quoted_cents:
            letter.last_error = (
                f"Paid {event.amount_cents} but quoted {letter.quoted_cents}; held for review."
            )
            move(db, letter, LetterStatus.FAILED, source="payment", detail=letter.last_error)
            return letter
        letter.amount_paid_cents = event.amount_cents or letter.quoted_cents
        letter.payment_reference = event.payment_reference
        letter.paid_at = utcnow()
        move(db, letter, LetterStatus.PAID, source="payment")
        return letter

    if event.kind is PaymentEventKind.FAILED:
        move(db, letter, LetterStatus.FAILED, source="payment", detail="The payment failed.")
        return letter

    if event.kind is PaymentEventKind.EXPIRED:
        if is_chargeable(LetterStatus(letter.status)):
            move(
                db,
                letter,
                LetterStatus.CANCELED,
                source="payment",
                detail="The checkout session expired before payment.",
            )
        return letter

    if event.kind is PaymentEventKind.REFUNDED:
        letter.refunded_at = utcnow()
        letter.status_detail = "Refunded."
        return letter

    return letter


def handle_mail_event(db: Session, *, event: ProviderEvent) -> Letter | None:
    """Apply a verified mailing-provider event."""
    letter = None
    if event.provider_letter_id:
        letter = db.execute(
            select(Letter).where(Letter.provider_letter_id == event.provider_letter_id)
        ).scalar_one_or_none()

    if not record_webhook(
        db,
        provider=event.provider,
        event_id=event.event_id,
        event_type=event.event_type,
        body=b"",
        letter_id=letter.id if letter else None,
    ):
        log.info("duplicate mail event %s ignored", event.event_id)
        return letter

    if letter is None:
        log.info("mail event %s does not match any letter", event.event_id)
        return None

    target = PROVIDER_EVENT_STATUS.get(event.event_type)
    if target is None:
        # Recorded, but an unrecognised event never invents a status.
        return letter

    try:
        move(db, letter, target, source="mail_provider", detail=event.event_type)
    except InvalidTransition:
        # Providers do not guarantee ordering; an out-of-order older event is
        # normal and must not be an error.
        log.info(
            "ignoring out-of-order mail event %s for letter %s (%s -> %s)",
            event.event_id,
            letter.id,
            letter.status,
            target,
        )
    return letter


# --------------------------------------------------------------------------
# submission
# --------------------------------------------------------------------------


def claim_for_submission(db: Session, letter: Letter) -> bool:
    """Move `paid -> submitting` and commit, before any provider call.

    Committing the claim first is what makes a crash safe: the letter is left in
    `submitting`, which the retry job treats as "we do not know", and which the
    provider's idempotency key resolves without a second envelope.
    """
    if LetterStatus(letter.status) is LetterStatus.SUBMITTING:
        return True
    if LetterStatus(letter.status) is not LetterStatus.PAID:
        return False
    move(db, letter, LetterStatus.SUBMITTING, source="mailer")
    letter.submit_attempts += 1
    db.commit()
    return True


def submit_letter(
    db: Session,
    *,
    settings: Settings,
    mail: MailProvider,
    payments: PaymentProvider | None,
    letter: Letter,
) -> Letter:
    """Hand a paid letter to the mailing provider. Safe to call more than once."""
    if not is_mailable(LetterStatus(letter.status)):
        return letter

    if not claim_for_submission(db, letter):
        return letter

    # A suppression added between payment and submission still wins.
    if is_suppressed(db, letter.address_hash):
        _fail_and_refund(
            db,
            settings=settings,
            payments=payments,
            letter=letter,
            reason="This address is on the do-not-mail list.",
        )
        return letter

    doc = compose_letter(
        LetterInput(
            address=recipient_address(letter),
            observations=list(letter.observations),
            note=letter.note,
            suggestions=list(letter.suggestions),
            date_iso=letter.created_at.date().isoformat(),
        )
    )
    # The stored text is what the sender approved; if recomposition disagrees,
    # the template changed underneath a paid letter and we stop rather than
    # print something nobody read.
    if doc.plain_text != letter.letter_text:
        _fail_and_refund(
            db,
            settings=settings,
            payments=payments,
            letter=letter,
            reason="The letter template changed after this letter was approved.",
        )
        return letter

    try:
        result = mail.send_letter(
            SendLetterRequest(
                idempotency_key=letter.id,
                to_address=recipient_address(letter),
                from_address=UsAddress(
                    line1=settings.return_line1,
                    line2=settings.return_line2,
                    city=settings.return_city,
                    state=settings.return_state,
                    zip=settings.return_zip,
                ),
                from_name=settings.return_name,
                html=render_letter_html(doc),
                description=f"Why Is This Light On? letter {letter.id}",
                metadata={"letter_id": letter.id},
            )
        )
    except MailProviderError as exc:
        letter.last_error = str(exc)[:1000]
        if exc.retryable and letter.submit_attempts < MAX_SUBMIT_ATTEMPTS:
            # Back to `paid` so the retry job picks it up again.
            move(db, letter, LetterStatus.PAID, source="mailer", detail=str(exc)[:500])
            db.commit()
            return letter
        _fail_and_refund(
            db,
            settings=settings,
            payments=payments,
            letter=letter,
            reason=str(exc),
        )
        return letter

    letter.provider_letter_id = result.provider_id
    letter.mail_provider = result.provider
    letter.submitted_at = utcnow()
    letter.expected_delivery_date = (
        result.expected_delivery_date.isoformat() if result.expected_delivery_date else None
    )
    letter.purge_after = utcnow() + timedelta(days=settings.retention_days)
    move(
        db,
        letter,
        LetterStatus.SUBMITTED,
        source="mailer",
        detail="Accepted by the mailing provider for printing and posting.",
    )
    try:
        db.commit()
    except IntegrityError:
        # provider_letter_id is unique: another worker recorded this letter
        # first. That is the outcome we wanted, so let theirs stand.
        db.rollback()
    return letter


def _fail_and_refund(
    db: Session,
    *,
    settings: Settings,
    payments: PaymentProvider | None,
    letter: Letter,
    reason: str,
) -> None:
    letter.last_error = reason[:1000]
    refunded = False
    if payments is not None and letter.payment_reference and letter.refunded_at is None:
        try:
            payments.refund(letter.payment_reference, reason=reason)
            letter.refunded_at = utcnow()
            refunded = True
        except PaymentError as exc:
            log.error("refund failed for letter %s: %s", letter.id, exc)

    detail = reason
    if refunded:
        detail = f"{reason} Your payment has been refunded in full."
    elif letter.payment_reference:
        detail = f"{reason} We could not process the refund automatically; we will do it by hand."

    move(db, letter, LetterStatus.FAILED, source="mailer", detail=detail)
    letter.purge_after = utcnow() + timedelta(days=settings.retention_days)
    db.commit()


def find_retryable(db: Session, *, older_than_minutes: int = 5) -> list[Letter]:
    """Letters that are paid but unmailed, or stuck mid-submission."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    return list(
        db.execute(
            select(Letter).where(
                Letter.status.in_([LetterStatus.PAID.value, LetterStatus.SUBMITTING.value]),
                Letter.updated_at < cutoff,
                Letter.submit_attempts < MAX_SUBMIT_ATTEMPTS,
            )
        ).scalars()
    )


# --------------------------------------------------------------------------
# retention
# --------------------------------------------------------------------------


def purge_expired(db: Session, *, now: datetime | None = None) -> int:
    """Blank the personal data on letters past their retention date.

    The row survives, because the address hash and the outcome are what enforce
    a cooldown and a do-not-mail request. Everything that could reconstruct the
    letter is cleared.
    """
    current = now or datetime.now(timezone.utc)
    rows = db.execute(
        select(Letter).where(
            Letter.purged.is_(False),
            Letter.purge_after.isnot(None),
            Letter.purge_after < current,
        )
    ).scalars()

    count = 0
    for letter in rows:
        letter.to_line1 = ""
        letter.to_line2 = ""
        letter.to_city = ""
        letter.to_state = ""
        letter.to_zip = ""
        letter.note = ""
        letter.letter_text = ""
        letter.sender_email = ""
        letter.purged = True
        count += 1
    return count
