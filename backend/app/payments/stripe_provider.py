"""Stripe Checkout.

Two decisions worth stating, because both are load-bearing:

1. **The success redirect is not evidence of payment.** Stripe's own guidance is
   to fulfil on `checkout.session.completed` (plus
   `checkout.session.async_payment_succeeded` for payment methods that settle
   later). This provider therefore only ever reports PAID from a webhook, and
   `services.mailing` is the only caller. A browser landing on the success URL
   causes a status page to be rendered and nothing else.

2. **Signature verification is ours, not the SDK's.** `core.security` implements
   Stripe's documented `Stripe-Signature` scheme with a constant-time compare
   and a replay window. That keeps the code that decides "we were paid" short,
   readable and unit-tested without the vendor package installed. The SDK is
   still used for API calls, imported lazily so this module can be imported —
   and its webhook handling tested — anywhere.
"""

from __future__ import annotations

import json
from typing import Any

from app.core.security import SignatureError, verify_stripe_signature

from .base import (
    CheckoutRequest,
    CheckoutSession,
    PaymentError,
    PaymentEvent,
    PaymentEventKind,
)

#: Events that mean money arrived. Nothing else can produce PAID.
PAID_EVENTS = frozenset({"checkout.session.completed", "checkout.session.async_payment_succeeded"})
FAILED_EVENTS = frozenset({"checkout.session.async_payment_failed"})
EXPIRED_EVENTS = frozenset({"checkout.session.expired"})
REFUND_EVENTS = frozenset({"charge.refunded"})


class StripePaymentProvider:
    name = "stripe"

    def __init__(self, secret_key: str, webhook_secret: str) -> None:
        if not secret_key:
            raise ValueError("A Stripe secret key is required.")
        if not webhook_secret:
            raise ValueError("A Stripe webhook signing secret is required.")
        self._secret_key = secret_key
        self._webhook_secret = webhook_secret

    @property
    def can_charge_real_money(self) -> bool:
        return self._secret_key.startswith("sk_live_")

    def _stripe(self) -> Any:
        try:
            import stripe
        except ImportError as exc:  # pragma: no cover - dependency is pinned
            raise PaymentError(
                "The stripe package is not installed but PAYMENT_PROVIDER=stripe.",
                retryable=False,
            ) from exc
        stripe.api_key = self._secret_key
        return stripe

    # --- checkout ---------------------------------------------------------

    def create_checkout_session(self, request: CheckoutRequest) -> CheckoutSession:
        stripe = self._stripe()
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                success_url=request.success_url,
                cancel_url=request.cancel_url,
                customer_email=request.customer_email,
                # Our letter id, so the webhook can find the record without
                # trusting anything the browser sends back.
                client_reference_id=request.letter_id,
                metadata={"letter_id": request.letter_id, **request.metadata},
                payment_intent_data={
                    "metadata": {"letter_id": request.letter_id},
                    "description": request.description[:200],
                },
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": request.currency,
                            "unit_amount": request.amount_cents,
                            "product_data": {
                                "name": "One printed and posted letter",
                                "description": request.description[:200],
                            },
                        },
                    }
                ],
                # Stripe deduplicates on this key, so a retried confirmation
                # returns the original session instead of a second charge.
                idempotency_key=request.idempotency_key,
            )
        except Exception as exc:
            raise PaymentError(f"Stripe refused to open a checkout session: {exc}") from exc

        if not session.get("url"):
            raise PaymentError("Stripe returned no checkout URL.", retryable=False)

        return CheckoutSession(
            provider=self.name, session_id=str(session["id"]), url=str(session["url"])
        )

    # --- webhooks ---------------------------------------------------------

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> PaymentEvent:
        lower = {k.lower(): v for k, v in headers.items()}
        try:
            verify_stripe_signature(body, lower.get("stripe-signature", ""), self._webhook_secret)
        except SignatureError as exc:
            raise PaymentError(str(exc), retryable=False) from exc

        payload = json.loads(body.decode("utf-8"))
        event_type = str(payload.get("type", ""))
        obj = (payload.get("data") or {}).get("object") or {}

        if event_type in PAID_EVENTS:
            # A session can complete while the payment is still pending for
            # delayed payment methods; only `paid` means the money is there.
            if str(obj.get("payment_status", "paid")) != "paid":
                kind = PaymentEventKind.IGNORED
            else:
                kind = PaymentEventKind.PAID
        elif event_type in FAILED_EVENTS:
            kind = PaymentEventKind.FAILED
        elif event_type in EXPIRED_EVENTS:
            kind = PaymentEventKind.EXPIRED
        elif event_type in REFUND_EVENTS:
            kind = PaymentEventKind.REFUNDED
        else:
            kind = PaymentEventKind.IGNORED

        metadata = obj.get("metadata") or {}
        letter_id = obj.get("client_reference_id") or metadata.get("letter_id")

        return PaymentEvent(
            provider=self.name,
            event_id=str(payload.get("id", "")),
            kind=kind,
            letter_id=str(letter_id) if letter_id else None,
            session_id=str(obj.get("id")) if obj.get("id") else None,
            payment_reference=_payment_reference(obj),
            amount_cents=obj.get("amount_total") or obj.get("amount"),
            currency=obj.get("currency"),
            raw=payload,
        )

    # --- refunds ----------------------------------------------------------

    def refund(self, payment_reference: str, *, reason: str) -> None:
        stripe = self._stripe()
        try:
            stripe.Refund.create(
                payment_intent=payment_reference,
                metadata={"reason": reason[:200]},
                # Safe to retry: Stripe will not refund twice for one key.
                idempotency_key=f"refund_{payment_reference}",
            )
        except Exception as exc:
            raise PaymentError(f"Stripe refund failed: {exc}") from exc


def _payment_reference(obj: dict) -> str | None:
    intent = obj.get("payment_intent")
    if isinstance(intent, str):
        return intent
    if isinstance(intent, dict):
        return str(intent.get("id"))
    if obj.get("object") == "charge":
        return str(obj.get("payment_intent") or obj.get("id"))
    return None
