"""The payment-provider interface.

Deliberately small. The app needs to open a hosted checkout page, recognise a
signed "this was paid" event, and refund. It never handles a card number, never
stores one, and never decides on its own that a payment succeeded.

The one rule encoded in the shape of this interface: `parse_webhook` is the only
function that can produce a `PaymentEvent`, and only a `PaymentEvent` can move a
letter to `paid`. The browser's redirect to the success URL carries no
authority; it is a navigation, and anyone can navigate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class PaymentEventKind(StrEnum):
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"
    IGNORED = "ignored"


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    provider: str
    session_id: str
    url: str


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    letter_id: str
    amount_cents: int
    currency: str
    description: str
    success_url: str
    cancel_url: str
    #: Reused across retries for the same confirmation attempt.
    idempotency_key: str
    customer_email: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    provider: str
    event_id: str
    kind: PaymentEventKind
    letter_id: str | None
    session_id: str | None
    payment_reference: str | None
    amount_cents: int | None
    currency: str | None
    raw: dict


class PaymentError(Exception):
    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@runtime_checkable
class PaymentProvider(Protocol):
    name: str

    @property
    def can_charge_real_money(self) -> bool: ...

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession: ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent: ...

    def refund(self, payment_reference: str, *, reason: str) -> None: ...
