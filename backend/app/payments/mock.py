"""A payment provider that cannot charge anything.

It issues a checkout URL pointing at a local page that lets a developer simulate
the webhook. It never contacts a payment network, and `can_charge_real_money` is
a hard-coded False so no configuration mistake can turn it into one.
"""

from __future__ import annotations

import hashlib
import json

from .base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentEvent,
    PaymentEventKind,
)


class MockPaymentProvider:
    name = "mock"

    def __init__(self, dev_checkout_url: str = "/api/v1/dev/checkout") -> None:
        self._dev_checkout_url = dev_checkout_url
        self.refunds: list[tuple[str, str]] = []

    @property
    def can_charge_real_money(self) -> bool:
        return False

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        # Derived from the idempotency key, so retrying a confirmation returns
        # the same session id rather than a second one.
        session_id = (
            "cs_mock_" + hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()[:24]
        )
        return CheckoutSession(
            provider=self.name,
            session_id=session_id,
            url=(
                f"{self._dev_checkout_url}?session={session_id}"
                f"&letter={request.letter_id}&amount={request.amount_cents}"
            ),
        )

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        del headers
        payload = json.loads(body.decode("utf-8"))
        kind_raw = str(payload.get("kind", "paid"))
        kind = (
            PaymentEventKind(kind_raw)
            if kind_raw in set(PaymentEventKind)
            else PaymentEventKind.IGNORED
        )
        return PaymentEvent(
            provider=self.name,
            event_id=str(payload.get("id", "evt_mock")),
            kind=kind,
            letter_id=payload.get("letter_id"),
            session_id=payload.get("session_id"),
            payment_reference=payload.get("payment_reference", "pi_mock"),
            amount_cents=payload.get("amount_cents"),
            currency=payload.get("currency", "usd"),
            raw=payload,
        )

    def refund(self, payment_reference: str, *, reason: str) -> None:
        self.refunds.append((payment_reference, reason))
