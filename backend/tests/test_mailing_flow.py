"""The money-and-mail path, end to end, against mock providers.

These are the tests that would catch the failures that actually hurt someone:
charging twice, mailing twice, mailing without payment, mailing to a suppressed
address, or taking money and posting nothing.

Requires a database, so it runs under pytest (`cd backend && pytest`) rather
than the dependency-free runner.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import Letter, Suppression, WebhookEvent
from app.letters.address import UsAddress, address_hash
from app.letters.composer import LetterInput, compose_letter, letter_fingerprint
from app.payments.base import PaymentEvent, PaymentEventKind
from app.providers.base import ProviderEvent
from app.services import mailing
from app.services.state import LetterStatus

ADDRESS = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")


def _fingerprint(address: UsAddress = ADDRESS, **kwargs) -> str:
    doc = compose_letter(
        LetterInput(
            address=address,
            observations=kwargs.get("observations", ["all_night"]),
            note=kwargs.get("note", ""),
            suggestions=kwargs.get("suggestions", ["shield"]),
            date_iso=mailing.today_iso(),
        )
    )
    return letter_fingerprint(doc.plain_text)


def _draft(db, settings, address: UsAddress = ADDRESS, **kwargs) -> Letter:
    letter, _ = mailing.create_draft(
        db,
        settings=settings,
        address=address,
        observations=kwargs.get("observations", ["all_night"]),
        note=kwargs.get("note", ""),
        suggestions=kwargs.get("suggestions", ["shield"]),
        client_fingerprint=None,
        sender_email=kwargs.get("email", "sender@example.com"),
        client_hash="client-hash",
    )
    db.commit()
    return letter


def _pay(db, settings, letter: Letter, *, event_id: str = "evt_pay_1", amount: int | None = None):
    event = PaymentEvent(
        provider="mock",
        event_id=event_id,
        kind=PaymentEventKind.PAID,
        letter_id=letter.id,
        session_id="cs_1",
        payment_reference="pi_1",
        amount_cents=amount if amount is not None else letter.quoted_cents,
        currency="usd",
        raw={},
    )
    result = mailing.handle_payment_event(db, settings=settings, event=event)
    db.commit()
    return result


# --- drafts ---------------------------------------------------------------


def test_a_draft_stores_the_letter_the_server_composed(db, settings) -> None:
    letter = _draft(db, settings)
    assert letter.status == LetterStatus.DRAFT.value
    assert letter.letter_text.startswith(
        mailing.compose_letter(
            LetterInput(
                address=ADDRESS,
                observations=["all_night"],
                suggestions=["shield"],
                date_iso=mailing.today_iso(),
            )
        ).date
    )
    assert letter.letter_fingerprint == _fingerprint()
    assert letter.quoted_cents == settings.total_price_cents


def test_a_draft_is_refused_when_the_browsers_letter_differs_from_the_servers(db, settings) -> None:
    """The check that stops a modified client from printing something else."""
    with pytest.raises(mailing.ServiceError) as exc:
        mailing.create_draft(
            db,
            settings=settings,
            address=ADDRESS,
            observations=["all_night"],
            note="",
            suggestions=["shield"],
            client_fingerprint="deadbeef",
            sender_email="sender@example.com",
            client_hash="c",
        )
    assert exc.value.code == "fingerprint_mismatch"


def test_a_matching_fingerprint_is_accepted(db, settings) -> None:
    letter, _ = mailing.create_draft(
        db,
        settings=settings,
        address=ADDRESS,
        observations=["all_night"],
        note="",
        suggestions=["shield"],
        client_fingerprint=_fingerprint(),
        sender_email="sender@example.com",
        client_hash="c",
    )
    assert letter.id


# --- payment --------------------------------------------------------------


def test_a_letter_is_only_paid_by_a_payment_event(db, settings) -> None:
    letter = _draft(db, settings)
    assert letter.status == LetterStatus.DRAFT.value
    _pay(db, settings, letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.PAID.value
    assert letter.paid_at is not None
    assert letter.amount_paid_cents == letter.quoted_cents


def test_a_replayed_payment_event_is_ignored(db, settings) -> None:
    """The duplicate-payment defence: same event id, processed once."""
    letter = _draft(db, settings)
    _pay(db, settings, letter, event_id="evt_same")
    db.refresh(letter)
    first_paid_at = letter.paid_at

    _pay(db, settings, letter, event_id="evt_same")
    db.refresh(letter)
    assert letter.paid_at == first_paid_at
    assert db.execute(select(WebhookEvent)).scalars().all().__len__() == 1


def test_a_payment_for_the_wrong_amount_is_held_rather_than_mailed(db, settings) -> None:
    letter = _draft(db, settings)
    _pay(db, settings, letter, amount=1)
    db.refresh(letter)
    assert letter.status == LetterStatus.FAILED.value
    assert "quoted" in letter.last_error


def test_an_expired_checkout_cancels_an_unpaid_draft(db, settings) -> None:
    letter = _draft(db, settings)
    mailing.handle_payment_event(
        db,
        settings=settings,
        event=PaymentEvent(
            provider="mock",
            event_id="evt_expired",
            kind=PaymentEventKind.EXPIRED,
            letter_id=letter.id,
            session_id="cs_1",
            payment_reference=None,
            amount_cents=None,
            currency="usd",
            raw={},
        ),
    )
    db.commit()
    db.refresh(letter)
    assert letter.status == LetterStatus.CANCELED.value


# --- checkout idempotency -------------------------------------------------


def test_the_same_idempotency_key_returns_the_same_checkout_session(
    db, settings, providers
) -> None:
    _, payments = providers
    letter = _draft(db, settings)

    first = mailing.start_checkout(
        db, settings=settings, payments=payments, letter=letter, idempotency_key="key-1"
    )
    db.commit()
    second = mailing.start_checkout(
        db, settings=settings, payments=payments, letter=letter, idempotency_key="key-1"
    )
    db.commit()
    assert first == second


def test_reusing_an_idempotency_key_for_a_different_letter_is_refused(
    db, settings, providers
) -> None:
    _, payments = providers
    a = _draft(db, settings)
    b = _draft(db, settings, address=UsAddress("9 Highland Ave", "", "Somerville", "MA", "02143"))

    mailing.start_checkout(db, settings=settings, payments=payments, letter=a, idempotency_key="k")
    db.commit()
    with pytest.raises(mailing.ServiceError) as exc:
        mailing.start_checkout(
            db, settings=settings, payments=payments, letter=b, idempotency_key="k"
        )
    assert exc.value.code == "idempotency_conflict"


def test_a_letter_past_payment_cannot_open_another_checkout(db, settings, providers) -> None:
    _, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    with pytest.raises(mailing.ServiceError) as exc:
        mailing.start_checkout(
            db, settings=settings, payments=payments, letter=letter, idempotency_key="k2"
        )
    assert exc.value.code == "not_chargeable"


# --- submission -----------------------------------------------------------


def test_a_paid_letter_is_submitted_once_and_recorded(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)

    assert letter.status == LetterStatus.SUBMITTED.value
    assert letter.provider_letter_id
    assert letter.submitted_at is not None
    assert letter.purge_after is not None


def test_submitting_twice_does_not_produce_a_second_letter(db, settings, providers) -> None:
    """The duplicate-mail defence, at the level the app controls."""
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    first_id = letter.provider_letter_id
    first_at = letter.submitted_at

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.provider_letter_id == first_id
    assert letter.submitted_at == first_at
    assert letter.submit_attempts == 1


def test_an_unpaid_letter_is_never_submitted(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.DRAFT.value
    assert letter.provider_letter_id is None


def test_the_provider_idempotency_key_is_the_letter_id(db, settings, providers) -> None:
    """Even a duplicate call reaching the provider resolves to one envelope."""
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)

    seen: list[str] = []
    original = mail.send_letter

    def spy(request):
        seen.append(request.idempotency_key)
        return original(request)

    mail.send_letter = spy  # type: ignore[method-assign]
    try:
        mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    finally:
        mail.send_letter = original  # type: ignore[method-assign]

    assert seen == [letter.id]


def test_a_retryable_provider_failure_returns_the_letter_to_paid(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(
        db, settings, address=UsAddress("5 Provider Down Ln", "", "Marfa", "TX", "79843")
    )
    _pay(db, settings, letter)

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.PAID.value
    assert letter.submit_attempts == 1
    assert "unavailable" in letter.last_error


def test_repeated_retryable_failures_eventually_fail_and_refund(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(
        db, settings, address=UsAddress("5 Provider Down Ln", "", "Marfa", "TX", "79843")
    )
    _pay(db, settings, letter)

    for _ in range(mailing.MAX_SUBMIT_ATTEMPTS + 1):
        mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
        db.refresh(letter)

    assert letter.status == LetterStatus.FAILED.value
    assert letter.refunded_at is not None
    assert tuple(r[0] for r in payments.refunds) == ("pi_1",)
    assert "refunded in full" in letter.status_detail


def test_a_permanent_provider_rejection_refunds_immediately(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(
        db, settings, address=UsAddress("6 Provider Reject Ct", "", "Marfa", "TX", "79843")
    )
    _pay(db, settings, letter)

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.FAILED.value
    assert letter.submit_attempts == 1
    assert letter.refunded_at is not None


def test_a_suppression_added_after_payment_still_stops_the_letter(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)

    mailing.add_suppression(db, letter.address_hash, source="test")
    db.commit()

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.FAILED.value
    assert letter.provider_letter_id is None
    assert letter.refunded_at is not None
    assert "do-not-mail" in letter.status_detail


def test_a_template_change_after_approval_stops_the_letter(db, settings, providers) -> None:
    """Nobody's letter gets printed with words they did not read."""
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)

    letter.letter_text = letter.letter_text + "\nAn extra sentence nobody approved.\n"
    db.commit()

    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    assert letter.status == LetterStatus.FAILED.value
    assert letter.provider_letter_id is None
    assert "template changed" in letter.status_detail


def test_find_retryable_picks_up_stuck_letters(db, settings) -> None:
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    letter.updated_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()

    stuck = mailing.find_retryable(db)
    assert [row.id for row in stuck] == [letter.id]


# --- mailing-provider events ----------------------------------------------


def test_provider_events_advance_the_status(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)

    for index, (event_type, expected) in enumerate(
        [
            ("letter.in_transit", LetterStatus.IN_TRANSIT),
            ("letter.in_local_area", LetterStatus.IN_LOCAL_AREA),
            ("letter.processed_for_delivery", LetterStatus.PROCESSED_FOR_DELIVERY),
        ]
    ):
        mailing.handle_mail_event(
            db,
            event=ProviderEvent(
                provider="mock",
                event_id=f"evt_mail_{index}",
                event_type=event_type,
                provider_letter_id=letter.provider_letter_id,
                occurred_at=None,
                raw={},
            ),
        )
        db.commit()
        db.refresh(letter)
        assert letter.status == expected.value


def test_an_out_of_order_provider_event_does_not_move_the_letter_backwards(
    db, settings, providers
) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)

    for index, event_type in enumerate(["letter.processed_for_delivery", "letter.in_transit"]):
        mailing.handle_mail_event(
            db,
            event=ProviderEvent(
                provider="mock",
                event_id=f"evt_ooo_{index}",
                event_type=event_type,
                provider_letter_id=letter.provider_letter_id,
                occurred_at=None,
                raw={},
            ),
        )
        db.commit()
    db.refresh(letter)
    assert letter.status == LetterStatus.PROCESSED_FOR_DELIVERY.value


def test_an_unrecognised_provider_event_is_recorded_but_changes_nothing(
    db, settings, providers
) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)
    before = letter.status

    mailing.handle_mail_event(
        db,
        event=ProviderEvent(
            provider="mock",
            event_id="evt_unknown",
            event_type="letter.eaten_by_a_javelina",
            provider_letter_id=letter.provider_letter_id,
            occurred_at=None,
            raw={},
        ),
    )
    db.commit()
    db.refresh(letter)
    assert letter.status == before
    assert db.execute(
        select(WebhookEvent).where(WebhookEvent.event_id == "evt_unknown")
    ).scalar_one()


# --- policy ---------------------------------------------------------------


def test_a_recent_letter_puts_the_address_on_cooldown(db, settings) -> None:
    first = _draft(db, settings)
    _pay(db, settings, first)

    with pytest.raises(mailing.ServiceError) as exc:
        _draft(db, settings)
    assert exc.value.code == "cooldown"


def test_an_unpaid_draft_does_not_start_a_cooldown(db, settings) -> None:
    _draft(db, settings)
    second = _draft(db, settings)  # must not raise
    assert second.id


def test_the_cooldown_expires(db, settings) -> None:
    first = _draft(db, settings)
    _pay(db, settings, first)
    first.created_at = datetime.now(UTC) - timedelta(days=settings.repeat_address_cooldown_days + 1)
    db.commit()

    assert _draft(db, settings).id


def test_a_suppressed_address_cannot_be_drafted_to(db, settings) -> None:
    mailing.add_suppression(db, address_hash(ADDRESS, settings.address_pepper), source="test")
    db.commit()
    with pytest.raises(mailing.ServiceError) as exc:
        _draft(db, settings)
    assert exc.value.code == "suppressed"


def test_suppressing_twice_is_not_an_error(db, settings) -> None:
    hashed = address_hash(ADDRESS, settings.address_pepper)
    mailing.add_suppression(db, hashed, source="test")
    mailing.add_suppression(db, hashed, source="test")
    db.commit()
    assert db.execute(select(Suppression)).scalars().all().__len__() == 1


def test_the_lifetime_cap_stops_an_address_being_written_to_forever(db, settings) -> None:
    for index in range(settings.max_letters_per_address_lifetime):
        letter = _draft(db, settings)
        _pay(db, settings, letter, event_id=f"evt_life_{index}")
        letter.created_at = datetime.now(UTC) - timedelta(days=400)
        db.commit()

    with pytest.raises(mailing.ServiceError) as exc:
        _draft(db, settings)
    assert exc.value.code == "lifetime_limit"


# --- retention ------------------------------------------------------------


def test_retention_erases_the_letter_but_keeps_the_hash_and_outcome(
    db, settings, providers
) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)
    db.refresh(letter)

    hashed = letter.address_hash
    purged = mailing.purge_expired(
        db, now=datetime.now(UTC) + timedelta(days=settings.retention_days + 1)
    )
    db.commit()
    db.refresh(letter)

    assert purged == 1
    assert letter.to_line1 == "" and letter.to_zip == "" and letter.letter_text == ""
    assert letter.sender_email == "" and letter.note == ""
    # Still enough to honour a cooldown and a do-not-mail request:
    assert letter.address_hash == hashed
    assert letter.status == LetterStatus.SUBMITTED.value
    assert letter.purged is True


def test_retention_leaves_letters_that_are_not_due(db, settings, providers) -> None:
    mail, payments = providers
    letter = _draft(db, settings)
    _pay(db, settings, letter)
    mailing.submit_letter(db, settings=settings, mail=mail, payments=payments, letter=letter)

    assert mailing.purge_expired(db, now=datetime.now(UTC)) == 0
    db.refresh(letter)
    assert letter.to_line1 == ADDRESS.line1
