"""Provider behaviour: the mock's determinism, and the rendering and event
parsing that the real providers depend on.

The single most important assertion in this file is that nothing which claims
to be a development provider can report itself as able to send real mail.
"""

from __future__ import annotations

import json
import time
from datetime import date

import httpx
import pytest

from app.core.security import _expected
from app.letters.address import UsAddress
from app.letters.composer import LetterInput, compose_letter
from app.letters.render import esc, render_letter_html
from app.payments.base import PaymentEventKind
from app.payments.mock import MockPaymentProvider
from app.payments.stripe_provider import StripePaymentProvider
from app.providers.base import Deliverability, MailProviderError, SendLetterRequest
from app.providers.mock import MockMailProvider
from app.providers.postgrid import PostGridMailProvider

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
    assert "2.5in" in html  # clears PostGrid's top_first_page address area
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


# --- the PostGrid mail provider -----------------------------------------------
#
# No real HTTP: an httpx.MockTransport answers each endpoint so the request
# shaping, response parsing and webhook handling are all exercised offline.

PG_SECRET = "webhook_secret_pg"


def _postgrid(handler, *, av_api_key: str | None = None) -> PostGridMailProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return PostGridMailProvider("test_sk_x", PG_SECRET, av_api_key=av_api_key, client=client)


def _json(payload: dict, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


def _contact(status: str, **overrides) -> dict:
    body = {
        "addressStatus": status,
        "addressLine1": "414 W SAN ANTONIO ST",
        "city": "MARFA",
        "provinceOrState": "TX",
        "postalOrZip": "79843",
    }
    body.update(overrides)
    return body


def test_a_postgrid_test_key_cannot_send_real_mail() -> None:
    assert _postgrid(lambda r: _json({})).can_send_real_mail is False
    live = PostGridMailProvider("live_sk_x", PG_SECRET, allow_live_key=True)
    assert live.can_send_real_mail is True


def test_postgrid_refuses_a_live_key_unless_explicitly_allowed() -> None:
    with pytest.raises(ValueError, match="Refusing a live PostGrid key"):
        PostGridMailProvider("live_sk_x", PG_SECRET, allow_live_key=False)


def test_postgrid_verify_via_contact_maps_the_address_status() -> None:
    # No Address Verification key: verify by creating a Print & Mail contact.
    cases = {
        "verified": Deliverability.DELIVERABLE,
        "corrected": Deliverability.DELIVERABLE_WITH_CHANGES,
        "failed": Deliverability.UNDELIVERABLE,
    }
    for raw, expected in cases.items():
        seen: dict = {}

        def handler(request: httpx.Request, raw=raw, seen=seen) -> httpx.Response:
            seen["path"] = request.url.path
            return _json(_contact(raw), status=201)

        result = _postgrid(handler).verify_address(ADDRESS)
        assert seen["path"] == "/print-mail/v1/contacts"
        assert result.status is expected
        if expected is Deliverability.UNDELIVERABLE:
            assert result.standardized is None
        else:
            assert result.standardized == UsAddress(
                "414 W SAN ANTONIO ST", "", "MARFA", "TX", "79843"
            )


def test_postgrid_verify_uses_the_av_api_when_a_key_is_configured() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["api_key"] = request.headers.get("x-api-key")
        seen["sent"] = json.loads(request.content)["address"]
        return _json(
            {
                "status": "success",
                "data": {
                    "status": "corrected",
                    "line1": "414 W SAN ANTONIO ST STE 2",
                    "city": "MARFA",
                    "provinceOrState": "TX",
                    "postalOrZip": "79843",
                    "errors": {},
                },
            }
        )

    provider = _postgrid(handler, av_api_key="test_sk_av")
    result = provider.verify_address(ADDRESS)
    assert seen["path"] == "/v1/addver/verifications"
    assert seen["api_key"] == "test_sk_av"
    # PostGrid's AV fields are provinceOrState / postalOrZip, not state / zipCode.
    assert seen["sent"]["provinceOrState"] == "TX"
    assert seen["sent"]["postalOrZip"] == "79843"
    assert result.status is Deliverability.DELIVERABLE_WITH_CHANGES
    assert result.standardized == UsAddress(
        "414 W SAN ANTONIO ST STE 2", "", "MARFA", "TX", "79843"
    )


def test_postgrid_verify_treats_a_failed_result_with_a_unit_error_as_needs_unit() -> None:
    # The AV API returns status=failed for a missing secondary unit; that is
    # recoverable, so it must not read as UNDELIVERABLE.
    def handler(request: httpx.Request) -> httpx.Response:
        return _json(
            {
                "data": {
                    "status": "failed",
                    "line1": "350 5TH AVE",
                    "city": "NEW YORK",
                    "provinceOrState": "NY",
                    "postalOrZip": "10118",
                    "errors": {"line1": ["Missing Value: Suite identifier"]},
                }
            }
        )

    result = _postgrid(handler, av_api_key="test_sk_av").verify_address(ADDRESS)
    assert result.status is Deliverability.NEEDS_UNIT
    assert result.standardized is not None


def test_postgrid_verify_flags_a_missing_unit_as_needs_unit() -> None:
    provider = _postgrid(
        lambda r: _json(
            _contact("corrected", addressErrors={"line1": ["Missing secondary unit number"]}),
            status=201,
        )
    )
    assert provider.verify_address(ADDRESS).status is Deliverability.NEEDS_UNIT


def test_postgrid_send_letter_posts_html_with_an_idempotency_key() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["idempotency"] = request.headers.get("Idempotency-Key")
        seen["api_key"] = request.headers.get("x-api-key")
        seen["body"] = json.loads(request.content)
        return _json({"id": "letter_abc", "status": "ready", "expectedDeliveryDate": "2026-09-15"})

    provider = _postgrid(handler)
    result = provider.send_letter(
        SendLetterRequest(
            idempotency_key="ltr_42",
            to_address=ADDRESS,
            from_address=RETURN,
            from_name="Why Is This Light On?",
            html="<html>hi</html>",
            description="a letter",
            metadata={"content_version": "1.1.0"},
        )
    )
    assert result.provider_id == "letter_abc"
    assert result.expected_delivery_date == date(2026, 9, 15)
    assert seen["path"] == "/print-mail/v1/letters"
    assert seen["idempotency"] == "ltr_42"
    assert seen["api_key"] == "test_sk_x"
    assert seen["body"]["html"] == "<html>hi</html>"
    assert seen["body"]["color"] is False
    assert seen["body"]["addressPlacement"] == "top_first_page"
    assert seen["body"]["to"]["provinceOrState"] == "TX"
    assert seen["body"]["metadata"] == {"content_version": "1.1.0"}


def test_postgrid_send_letter_distinguishes_retryable_from_permanent() -> None:
    down = _postgrid(lambda r: _json({"message": "upstream"}, status=503))
    try:
        down.send_letter(_send_request(ADDRESS))
    except MailProviderError as exc:
        assert exc.retryable is True
    else:  # pragma: no cover
        raise AssertionError("expected a retryable failure")

    rejected = _postgrid(lambda r: _json({"error": {"message": "bad address"}}, status=422))
    try:
        rejected.send_letter(_send_request(ADDRESS))
    except MailProviderError as exc:
        assert exc.retryable is False
        assert "bad address" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a permanent failure")


def _pg_signed(payload: dict) -> tuple[dict[str, str], bytes]:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    return {"PostGrid-Signature": f"t={ts},v1={_expected(PG_SECRET, ts, body)}"}, body


def test_postgrid_webhook_verifies_the_signature_and_synthesises_the_event_type() -> None:
    provider = _postgrid(lambda r: _json({}))

    headers, body = _pg_signed(
        {
            "id": "evt_1",
            "type": "letter.updated",
            "data": {"id": "letter_abc", "status": "printing"},
        }
    )
    event = provider.parse_webhook(headers, body)
    assert event.event_type == "letter.printing"
    assert event.provider_letter_id == "letter_abc"

    headers, body = _pg_signed(
        {
            "id": "evt_2",
            "type": "letter.updated",
            "data": {"id": "letter_abc", "status": "completed", "imbStatus": "out_for_delivery"},
        }
    )
    # imbStatus wins when both are present.
    assert provider.parse_webhook(headers, body).event_type == "letter.out_for_delivery"


def test_postgrid_webhook_rejects_a_bad_signature_and_a_jwt_body() -> None:
    provider = _postgrid(lambda r: _json({}))

    headers, body = _pg_signed({"id": "evt_1", "type": "letter.updated", "data": {"id": "x"}})
    bad = dict(headers)
    bad["PostGrid-Signature"] = "t=1,v1=" + "0" * 64
    try:
        provider.parse_webhook(bad, body)
    except MailProviderError as exc:
        assert exc.retryable is False
    else:  # pragma: no cover
        raise AssertionError("expected the signature check to fail")

    jwt_body = b"eyJhbGciOiJIUzI1NiJ9.eyJ0eXBlIjoibGV0dGVyLnVwZGF0ZWQifQ.sig"
    ts = str(int(time.time()))
    jwt_headers = {"PostGrid-Signature": f"t={ts},v1={_expected(PG_SECRET, ts, jwt_body)}"}
    try:
        provider.parse_webhook(jwt_headers, jwt_body)
    except MailProviderError as exc:
        assert "JSON" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected the JWT body to be refused")
