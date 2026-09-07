"""The state machine and the pricing rules.

The state machine is where "a retry cannot mail twice" is enforced, so these
tests are written as statements about what must be impossible, not as a
transcription of the transition table.
"""

from __future__ import annotations

from app.services.pricing import build_quote, estimate_pages
from app.services.state import (
    COUNTS_TOWARD_COOLDOWN,
    PROVIDER_EVENT_STATUS,
    InvalidTransition,
    LetterStatus,
    assert_transition,
    can_transition,
    is_chargeable,
    is_mailable,
)

# --- state ----------------------------------------------------------------


def test_a_letter_cannot_be_mailed_before_it_is_paid_for() -> None:
    for status in (LetterStatus.DRAFT, LetterStatus.PENDING_PAYMENT):
        assert not is_mailable(status)
        assert not can_transition(status, LetterStatus.SUBMITTING)
        assert not can_transition(status, LetterStatus.SUBMITTED)


def test_only_paid_and_submitting_are_mailable() -> None:
    mailable = {s for s in LetterStatus if is_mailable(s)}
    assert mailable == {LetterStatus.PAID, LetterStatus.SUBMITTING}


def test_a_submitted_letter_can_never_go_back_to_paid_or_submitting() -> None:
    """The one-way door. Going back would allow a second envelope."""
    assert not can_transition(LetterStatus.SUBMITTED, LetterStatus.PAID)
    assert not can_transition(LetterStatus.SUBMITTED, LetterStatus.SUBMITTING)
    assert not can_transition(LetterStatus.SUBMITTED, LetterStatus.DRAFT)
    for downstream in (
        LetterStatus.IN_TRANSIT,
        LetterStatus.IN_LOCAL_AREA,
        LetterStatus.PROCESSED_FOR_DELIVERY,
        LetterStatus.RETURNED_TO_SENDER,
    ):
        assert not can_transition(downstream, LetterStatus.PAID)
        assert not can_transition(downstream, LetterStatus.SUBMITTING)


def test_a_failed_submission_can_be_retried_from_submitting() -> None:
    assert can_transition(LetterStatus.SUBMITTING, LetterStatus.PAID)
    assert can_transition(LetterStatus.SUBMITTING, LetterStatus.FAILED)


def test_canceled_and_returned_are_dead_ends() -> None:
    for status in (LetterStatus.CANCELED, LetterStatus.RETURNED_TO_SENDER):
        for target in LetterStatus:
            if target == status:
                continue
            assert not can_transition(status, target), f"{status} -> {target} should be impossible"


def test_repeating_the_same_status_is_allowed_so_replays_are_harmless() -> None:
    for status in LetterStatus:
        assert can_transition(status, status)


def test_assert_transition_raises_with_both_states_named() -> None:
    try:
        assert_transition(LetterStatus.DRAFT, LetterStatus.SUBMITTED)
    except InvalidTransition as exc:
        assert exc.current is LetterStatus.DRAFT
        assert exc.target is LetterStatus.SUBMITTED
    else:  # pragma: no cover
        raise AssertionError("expected InvalidTransition")


def test_only_draft_and_pending_payment_are_chargeable() -> None:
    chargeable = {s for s in LetterStatus if is_chargeable(s)}
    assert chargeable == {LetterStatus.DRAFT, LetterStatus.PENDING_PAYMENT}


def test_unpaid_drafts_do_not_consume_an_addresss_cooldown() -> None:
    assert LetterStatus.DRAFT not in COUNTS_TOWARD_COOLDOWN
    assert LetterStatus.PENDING_PAYMENT not in COUNTS_TOWARD_COOLDOWN
    assert LetterStatus.CANCELED not in COUNTS_TOWARD_COOLDOWN
    assert LetterStatus.SUBMITTED in COUNTS_TOWARD_COOLDOWN


def test_provider_events_only_ever_map_to_post_submission_statuses() -> None:
    downstream = {
        LetterStatus.SUBMITTED,
        LetterStatus.IN_TRANSIT,
        LetterStatus.IN_LOCAL_AREA,
        LetterStatus.PROCESSED_FOR_DELIVERY,
        LetterStatus.RETURNED_TO_SENDER,
    }
    for event, status in PROVIDER_EVENT_STATUS.items():
        assert status in downstream, f"{event} maps to {status}, which the provider must not set"


def test_no_provider_event_can_mark_a_letter_paid_or_delivered() -> None:
    assert LetterStatus.PAID not in PROVIDER_EVENT_STATUS.values()
    # There is deliberately no "delivered" state at all.
    assert not any(s.value == "delivered" for s in LetterStatus)


# --- pricing --------------------------------------------------------------


def test_the_quote_total_is_the_sum_of_its_lines() -> None:
    quote = build_quote(postage_cents=174, printing_cents=95, service_cents=80)
    assert quote.total_cents == sum(line.cents for line in quote.lines) == 349
    assert quote.currency == "usd"


def test_a_second_page_costs_a_second_sheet_of_printing_only() -> None:
    one = build_quote(postage_cents=174, printing_cents=95, service_cents=80, pages=1)
    two = build_quote(postage_cents=174, printing_cents=95, service_cents=80, pages=2)
    assert two.total_cents - one.total_cents == 95
    assert "2 pages" in two.lines[0].label


def test_page_counts_outside_what_the_template_can_produce_are_refused() -> None:
    for pages in (0, -1, 3, 99):
        try:
            build_quote(postage_cents=1, printing_cents=1, service_cents=1, pages=pages)
        except ValueError:
            continue
        raise AssertionError(f"expected {pages} pages to be refused")  # pragma: no cover


def test_the_quote_says_what_cannot_be_promised() -> None:
    quote = build_quote(postage_cents=174, printing_cents=95, service_cents=80)
    assert "estimate" in quote.delivery_estimate.lower()
    assert "not a guarantee" in quote.delivery_estimate.lower()
    assert "no delivery confirmation" in quote.delivery_estimate.lower()
    assert "refund" in quote.disclaimer.lower()


def test_page_estimate_matches_what_the_letter_actually_prints() -> None:
    """Calibrated against the rendered PDF, not guessed.

    A short letter is one page; the longest the template can produce — every
    observation, a full note, every suggestion — is two.
    """
    from app.letters.address import UsAddress
    from app.letters.composer import LetterInput, compose_letter

    address = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")

    shortest = compose_letter(LetterInput(address=address, date_iso="2026-09-07"))
    assert estimate_pages(shortest.plain_text) == 1

    typical = compose_letter(
        LetterInput(
            address=address,
            observations=["all_night", "upward"],
            suggestions=["shield", "timer", "warmer_color"],
            date_iso="2026-09-07",
        )
    )
    assert estimate_pages(typical.plain_text) == 1

    longest = compose_letter(
        LetterInput(
            address=address,
            observations=["all_night", "upward", "spill", "unused_area", "other"],
            note="x" * 200,
            suggestions=[
                "turn_off",
                "timer",
                "motion_sensor",
                "shield",
                "lower_brightness",
                "warmer_color",
            ],
            date_iso="2026-09-07",
        )
    )
    assert estimate_pages(longest.plain_text) == 2
