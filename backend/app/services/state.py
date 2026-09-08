"""The letter state machine.

Every transition a letter can make is listed here, and `assert_transition` is
the only way state changes. That is what makes "a retry cannot mail twice" a
property of the code rather than a habit: `paid -> submitting -> submitted` are
one-way doors, and there is no edge back into `paid` from anything downstream.

Terminology matters on the way out of this module: `submitted` means the mailing
provider accepted the letter, and nothing here ever claims delivery. The
provider-reported statuses below are the furthest we can honestly go.
"""

from __future__ import annotations

from enum import StrEnum


class LetterStatus(StrEnum):
    # Ours
    DRAFT = "draft"
    PENDING_PAYMENT = "pending_payment"
    PAID = "paid"
    SUBMITTING = "submitting"
    SUBMITTED = "submitted"
    FAILED = "failed"
    CANCELED = "canceled"
    # Provider-reported, downstream of submitted
    IN_TRANSIT = "in_transit"
    IN_LOCAL_AREA = "in_local_area"
    PROCESSED_FOR_DELIVERY = "processed_for_delivery"
    RETURNED_TO_SENDER = "returned_to_sender"


#: Statuses after which no money may be taken and no letter may be printed.
TERMINAL: frozenset[LetterStatus] = frozenset(
    {
        LetterStatus.SUBMITTED,
        LetterStatus.FAILED,
        LetterStatus.CANCELED,
        LetterStatus.IN_TRANSIT,
        LetterStatus.IN_LOCAL_AREA,
        LetterStatus.PROCESSED_FOR_DELIVERY,
        LetterStatus.RETURNED_TO_SENDER,
    }
)

#: Statuses that mean money has been captured.
PAID_STATES: frozenset[LetterStatus] = frozenset(
    {
        LetterStatus.PAID,
        LetterStatus.SUBMITTING,
        LetterStatus.SUBMITTED,
        LetterStatus.IN_TRANSIT,
        LetterStatus.IN_LOCAL_AREA,
        LetterStatus.PROCESSED_FOR_DELIVERY,
        LetterStatus.RETURNED_TO_SENDER,
    }
)

#: Statuses that count against the per-address cooldown. A draft nobody paid
#: for should not block a neighbour from writing.
COUNTS_TOWARD_COOLDOWN: frozenset[LetterStatus] = PAID_STATES

ALLOWED: dict[LetterStatus, frozenset[LetterStatus]] = {
    # FAILED is reachable directly so a payment event that arrives before the
    # draft was moved to PENDING_PAYMENT (e.g. a wrong-amount charge) can still
    # be held for review rather than crashing the webhook handler.
    LetterStatus.DRAFT: frozenset(
        {
            LetterStatus.PENDING_PAYMENT,
            LetterStatus.PAID,
            LetterStatus.CANCELED,
            LetterStatus.FAILED,
        }
    ),
    # PENDING_PAYMENT -> PAID is the only way money is recognised, and only a
    # verified webhook performs it.
    LetterStatus.PENDING_PAYMENT: frozenset(
        {LetterStatus.PAID, LetterStatus.CANCELED, LetterStatus.FAILED}
    ),
    LetterStatus.PAID: frozenset({LetterStatus.SUBMITTING, LetterStatus.FAILED}),
    # Back to PAID only so a crashed submission can be retried; never from a
    # state that might already have produced a letter at the printer.
    LetterStatus.SUBMITTING: frozenset(
        {LetterStatus.SUBMITTED, LetterStatus.FAILED, LetterStatus.PAID}
    ),
    LetterStatus.SUBMITTED: frozenset(
        {
            LetterStatus.IN_TRANSIT,
            LetterStatus.IN_LOCAL_AREA,
            LetterStatus.PROCESSED_FOR_DELIVERY,
            LetterStatus.RETURNED_TO_SENDER,
        }
    ),
    LetterStatus.IN_TRANSIT: frozenset(
        {
            LetterStatus.IN_LOCAL_AREA,
            LetterStatus.PROCESSED_FOR_DELIVERY,
            LetterStatus.RETURNED_TO_SENDER,
        }
    ),
    LetterStatus.IN_LOCAL_AREA: frozenset(
        {LetterStatus.PROCESSED_FOR_DELIVERY, LetterStatus.RETURNED_TO_SENDER}
    ),
    LetterStatus.PROCESSED_FOR_DELIVERY: frozenset({LetterStatus.RETURNED_TO_SENDER}),
    LetterStatus.RETURNED_TO_SENDER: frozenset(),
    LetterStatus.FAILED: frozenset({LetterStatus.PAID}),  # a manual retry after a fix
    LetterStatus.CANCELED: frozenset(),
}


# Named without an -Error suffix on purpose: it is part of this module's API and
# reads as `raise InvalidTransition(current, target)`.
class InvalidTransition(Exception):  # noqa: N818
    def __init__(self, current: LetterStatus, target: LetterStatus) -> None:
        super().__init__(f"Cannot move a letter from {current} to {target}.")
        self.current = current
        self.target = target


def can_transition(current: LetterStatus, target: LetterStatus) -> bool:
    if current == target:
        return True  # idempotent replays are not errors
    return target in ALLOWED[current]


def assert_transition(current: LetterStatus, target: LetterStatus) -> None:
    if not can_transition(current, target):
        raise InvalidTransition(current, target)


def is_mailable(status: LetterStatus) -> bool:
    """True only where handing the letter to the printer is still correct."""
    return status in {LetterStatus.PAID, LetterStatus.SUBMITTING}


def is_chargeable(status: LetterStatus) -> bool:
    """True only where opening a checkout session is still correct."""
    return status in {LetterStatus.DRAFT, LetterStatus.PENDING_PAYMENT}


#: Mapping from the mailing provider's vocabulary to ours. Anything not listed
#: is recorded as an event but does not move the letter's status — an unknown
#: provider event must never be able to invent a state.
# PostGrid reports an order lifecycle (`status`) and, for live US mail, a USPS
# IMb tracking state (`imbStatus`). The provider flattens both into
# `letter.<value>` event names. `completed` is PostGrid's ~10-12 day "probably
# delivered" approximation; we map it no further than `processed_for_delivery`
# because first-class mail has no delivery confirmation and this service never
# claims one.
PROVIDER_EVENT_STATUS: dict[str, LetterStatus] = {
    "letter.created": LetterStatus.SUBMITTED,
    "letter.ready": LetterStatus.SUBMITTED,
    "letter.printing": LetterStatus.SUBMITTED,
    "letter.entered_mail_stream": LetterStatus.IN_TRANSIT,
    "letter.out_for_delivery": LetterStatus.PROCESSED_FOR_DELIVERY,
    "letter.processed_for_delivery": LetterStatus.PROCESSED_FOR_DELIVERY,
    "letter.completed": LetterStatus.PROCESSED_FOR_DELIVERY,
    "letter.returned_to_sender": LetterStatus.RETURNED_TO_SENDER,
}
