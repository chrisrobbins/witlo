"""Provider behaviour: the mock's determinism, and the rendering and event
parsing that the real providers depend on.

The single most important assertion in this file is that nothing which claims
to be a development provider can report itself as able to send real mail.
"""

from __future__ import annotations

import json
import time
from datetime import date

from app.core.security import _expected
from app.letters.address import UsAddress
from app.letters.composer import LetterInput, compose_letter
from app.letters.render import esc, render_letter_html
from app.payments.base import PaymentEventKind
from app.payments.mock import MockPaymentProvider
from app.payments.stripe_provider import StripePaymentProvider
from app.providers.base import Deliverability, MailProviderError, SendLetterRequest
from app.providers.mock import MockMailProvider

ADDRESS = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")
RETURN = UsAddress("PO Drawer 1", "", "Marfa", "TX", "79843")


def _send_request(address: UsAddress, key: str = "ltr_test") -> SendLetterRequest:
    return SendLetterRequest(
        idempotency_key=key,
        to_address=address,
        from_address=RETURN,
        from_name="Why Is This Light On?",
        html="<html></html>",
        description="test",
    )


# --- the mock mail provider ------------------------------------------------


def test_the_mock_can_never_report_that_it_sends_real_mail() -> None:
    assert MockMailProvider().can_send_real_mail is False
    assert MockPaymentProvider().can_charge_real_money is False


def test_mock_verification_is_deterministic() -> None:
    provider = MockMailProvider()
    first = provider.verify_address(ADDRESS)
    second = provider.verify_address(ADDRESS)
    assert first == second
    assert first.status is Deliverability.DELIVERABLE


def test_mock_recognises_its_documented_test_addresses() -> None:
    provider = MockMailProvider()
    assert (
        provider.verify_address(UsAddress("1 Nowhere Rd", "", "Marfa", "TX", "00000")).status
        is Deliverability.UNDELIVERABLE
    )
    assert (
        provider.verify_address(UsAddress("1 Undeliverable Way", "", "Marfa", "TX", "79843")).status
        is Deliverability.UNDELIVERABLE
    )
    assert (
        provider.verify_address(UsAddress("2 Needs Unit Blvd", "", "Marfa", "TX", "79843")).status
        is Deliverability.NEEDS_UNIT
    )
    assert (
        provider.verify_address(
            UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843-1234")
        ).status
        is Deliverability.DELIVERABLE_WITH_CHANGES
    )


def test_mock_standardization_only_trims_the_zip_and_uppercases_the_state() -> None:
    provider = MockMailProvider()
    result = provider.verify_address(
        UsAddress("414 W San Antonio St", "", "Marfa", "tx", "79843-1234")
    )
    assert result.standardized == UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")


def test_mock_send_is_deterministic_and_keyed_on_the_letter_id() -> None:
    provider = MockMailProvider()
    a = provider.send_letter(_send_request(ADDRESS, "ltr_abc"))
    b = provider.send_letter(_send_request(ADDRESS, "ltr_abc"))
    c = provider.send_letter(_send_request(ADDRESS, "ltr_xyz"))
    assert a == b
    assert a.provider_id != c.provider_id
    assert a.provider_id.startswith("ltr_mock_")
    assert isinstance(a.expected_delivery_date, date)


def test_mock_failure_addresses_distinguish_retryable_from_permanent() -> None:
    provider = MockMailProvider()
    try:
        provider.send_letter(
            _send_request(UsAddress("5 Provider Down Ln", "", "Marfa", "TX", "79843"))
        )
    except MailProviderError as exc:
        assert exc.retryable is True
    else:  # pragma: no cover
        raise AssertionError("expected a retryable failure")

    try:
        provider.send_letter(
            _send_request(UsAddress("6 Provider Reject Ct", "", "Marfa", "TX", "79843"))
        )
    except MailProviderError as exc:
        assert exc.retryable is False
    else:  # pragma: no cover
        raise AssertionError("expected a permanent failure")


# --- rendering -------------------------------------------------------------


def test_rendered_html_escapes_everything_that_came_from_a_person() -> None:
    doc = compose_letter(
        LetterInput(
            address=UsAddress('414 "W" <San> Antonio St', "", "Marfa", "TX", "79843"),
            observations=["other"],
            note='He said "hi" & waved',
            suggestions=["shield"],
            date_iso="2026-09-07",
        )
    )
    html = render_letter_html(doc)
    # The composer strips angle brackets; the renderer escapes what remains.
    assert "<San>" not in html
    assert "&quot;" in html or "&#x27;" in html
    assert "&amp;" in html
    # Only our own tags survive.
    assert html.count("<script") == 0


def test_escaping_helper_covers_the_dangerous_characters() -> None:
    assert esc('<a href="x">&</a>') == "&lt;a href=&quot;x&quot;&gt;&amp;&lt;/a&gt;"


def test_rendered_html_reserves_the_envelope_window() -> None:
    doc = compose_letter(LetterInput(address=ADDRESS, date_iso="2026-09-07"))
    html = render_letter_html(doc)
    assert "2.5in" in html  # Lob's requirement for top_first_page
    assert 'class="window"' in html


def test_rendered_html_is_self_contained() -> None:
    """The print provider must not need to fetch anything to render this page.

    The one `http://` in the output is the SVG namespace declaration, which is
    an identifier rather than a URL that gets fetched — so this checks for the
    constructs that actually load a resource.
    """
    doc = compose_letter(LetterInput(address=ADDRESS, date_iso="2026-09-07"))
    html = render_letter_html(doc)
    for external in ("<script", "<link", "<img", "src=", "@import", 'href="http', "url(http"):
        assert external not in html, f"letter HTML reaches out for {external!r}"
    assert html.count("http") == 1  # the SVG xmlns and nothing else


# --- Stripe event parsing --------------------------------------------------


def _stripe_provider() -> StripePaymentProvider:
    return StripePaymentProvider("sk_test_x", "whsec_x")


def _signed(payload: dict, secret: str = "whsec_x") -> tuple[dict[str, str], bytes]:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    return {"Stripe-Signature": f"t={ts},v1={_expected(secret, ts, body)}"}, body


def test_only_a_completed_and_paid_session_counts_as_payment() -> None:
    provider = _stripe_provider()
    headers, body = _signed(
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_1",
                    "payment_status": "paid",
                    "client_reference_id": "ltr_1",
                    "amount_total": 349,
                    "currency": "usd",
                    "payment_intent": "pi_1",
                }
            },
        }
    )
    event = provider.parse_webhook(headers, body)
    assert event.kind is PaymentEventKind.PAID
    assert event.letter_id == "ltr_1"
    assert event.amount_cents == 349
    assert event.payment_reference == "pi_1"


def test_a_completed_session_that_is_not_yet_paid_is_ignored() -> None:
    """Delayed payment methods complete the session before the money arrives."""
    provider = _stripe_provider()
    headers, body = _signed(
        {
            "id": "evt_2",
            "type": "checkout.session.completed",
            "data": {
                "object": {"id": "cs_2", "payment_status": "unpaid", "client_reference_id": "ltr_2"}
            },
        }
    )
    assert provider.parse_webhook(headers, body).kind is PaymentEventKind.IGNORED


def test_async_success_failure_and_expiry_are_each_distinct() -> None:
    provider = _stripe_provider()
    cases = {
        "checkout.session.async_payment_succeeded": PaymentEventKind.PAID,
        "checkout.session.async_payment_failed": PaymentEventKind.FAILED,
        "checkout.session.expired": PaymentEventKind.EXPIRED,
        "charge.refunded": PaymentEventKind.REFUNDED,
        "customer.created": PaymentEventKind.IGNORED,
    }
    for event_type, expected in cases.items():
        headers, body = _signed(
            {
                "id": f"evt_{event_type}",
                "type": event_type,
                "data": {
                    "object": {
                        "id": "cs_x",
                        "payment_status": "paid",
                        "client_reference_id": "ltr_x",
                    }
                },
            }
        )
        assert provider.parse_webhook(headers, body).kind is expected, event_type


def test_a_stripe_test_key_cannot_charge_real_money() -> None:
    assert _stripe_provider().can_charge_real_money is False
    assert StripePaymentProvider("sk_live_x", "whsec_x").can_charge_real_money is True


def test_stripe_provider_refuses_to_exist_without_a_webhook_secret() -> None:
    for args in (("", "whsec_x"), ("sk_test_x", "")):
        try:
            StripePaymentProvider(*args)
        except ValueError:
            continue
        raise AssertionError(f"expected {args} to be refused")  # pragma: no cover


def test_the_mock_payment_session_id_is_stable_for_one_idempotency_key() -> None:
    from app.payments.base import CheckoutRequest

    provider = MockPaymentProvider()
    request = CheckoutRequest(
        letter_id="ltr_1",
        amount_cents=349,
        currency="usd",
        description="d",
        success_url="s",
        cancel_url="c",
        idempotency_key="key-1",
    )
    assert provider.create_checkout_session(request).session_id == (
        provider.create_checkout_session(request).session_id
    )
