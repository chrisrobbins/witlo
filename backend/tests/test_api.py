"""HTTP surface: validation, error shapes, webhook handling, CORS, demo safety.

Runs under pytest against the mock providers and a throwaway SQLite database.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.db.models import Letter
from app.db.session import SessionLocal
from app.services.state import LetterStatus

ADDRESS = {
    "line1": "414 W San Antonio St",
    "line2": "",
    "city": "Marfa",
    "state": "TX",
    "zip": "79843",
}


def _create(client, **overrides):
    payload = {
        "address": ADDRESS,
        "observations": ["all_night"],
        "note": "",
        "suggestions": ["shield"],
        "senderEmail": "sender@example.com",
    }
    payload.update(overrides)
    return client.post("/api/v1/letters", json=payload)


# --- health ---------------------------------------------------------------


def test_health_states_plainly_what_this_deployment_can_do(client) -> None:
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["mode"] == "demo"
    assert body["canSendRealMail"] is False
    assert body["canChargeRealMoney"] is False
    assert body["contentVersion"]


# --- address verification -------------------------------------------------


def test_verify_returns_the_standardized_address(client) -> None:
    response = client.post("/api/v1/addresses/verify", json={"address": ADDRESS})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "deliverable"
    assert body["standardized"]["state"] == "TX"
    assert body["suppressed"] is False
    assert body["cooldownUntil"] is None


def test_verify_rejects_a_po_box_with_a_readable_message(client) -> None:
    response = client.post(
        "/api/v1/addresses/verify", json={"address": {**ADDRESS, "line1": "PO Box 42"}}
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_address"
    assert "outdoor light" in response.json()["detail"]["detail"]


def test_verify_reports_an_undeliverable_address(client) -> None:
    response = client.post(
        "/api/v1/addresses/verify", json={"address": {**ADDRESS, "zip": "00000"}}
    )
    assert response.json()["status"] == "undeliverable"


def test_verify_reports_suppression(client) -> None:
    client.post("/api/v1/suppressions", json={"address": ADDRESS, "reason": "no thanks"})
    body = client.post("/api/v1/addresses/verify", json={"address": ADDRESS}).json()
    assert body["suppressed"] is True
    assert "asked not to receive" in body["message"]


# --- drafts ---------------------------------------------------------------


def test_creating_a_draft_returns_the_letter_and_a_priced_quote(client) -> None:
    response = _create(client)
    assert response.status_code == 200
    body = response.json()
    assert body["id"].startswith("ltr_")
    assert body["status"] == "draft"
    assert "Hello from a neighbor," in body["letterText"]
    assert body["quote"]["totalCents"] == sum(line["cents"] for line in body["quote"]["lines"])
    assert body["quote"]["totalCents"] > 0


def test_an_unknown_observation_is_rejected_by_the_schema(client) -> None:
    response = _create(client, observations=["all_night", "the_light_is_ugly"])
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_validation_errors_do_not_echo_the_address_back(client) -> None:
    """Pydantic's default error body would repeat the input into the response
    and the logs; the handler replaces it."""
    response = client.post(
        "/api/v1/letters",
        json={"address": {**ADDRESS, "state": "TEXAS"}, "observations": [], "suggestions": []},
    )
    assert response.status_code == 422
    assert "414 W San Antonio" not in response.text


def test_a_draft_to_a_suppressed_address_is_refused(client) -> None:
    client.post("/api/v1/suppressions", json={"address": ADDRESS})
    response = _create(client)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "suppressed"


def test_an_oversized_note_is_a_validation_error_not_a_silent_trim(client) -> None:
    response = _create(client, observations=["other"], note="x" * 400)
    assert response.status_code == 422


# --- the sender's date --------------------------------------------------------
#
# The browser dates the letter with its local clock, so a sender in the Americas
# late in the evening approves a letter dated a day before this server's UTC
# date. The server must date its copy the same way or the fingerprint check
# rejects a letter the sender read correctly.


def _fingerprint_for(date_iso: str) -> str:
    from app.letters.composer import LetterInput, compose_letter, letter_fingerprint

    doc = compose_letter(
        LetterInput(
            address=_domain_address(),
            observations=["all_night"],
            note="",
            suggestions=["shield"],
            date_iso=date_iso,
        )
    )
    return letter_fingerprint(doc.plain_text)


def _domain_address():
    from app.letters.address import UsAddress

    return UsAddress(**ADDRESS)


def test_a_client_date_one_day_off_is_honoured_not_rejected(client) -> None:
    from datetime import date, timedelta

    from app.letters.composer import format_letter_date

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    response = _create(client, dateIso=yesterday, letterFingerprint=_fingerprint_for(yesterday))
    assert response.status_code == 200
    # The letter is dated the sender's day, not the server's.
    assert format_letter_date(yesterday) in response.json()["letterText"]


def test_a_client_date_far_from_today_is_refused(client) -> None:
    from datetime import date, timedelta

    far = (date.today() + timedelta(days=30)).isoformat()
    response = _create(client, dateIso=far, letterFingerprint=_fingerprint_for(far))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "stale_date"


def test_a_malformed_client_date_is_a_validation_error(client) -> None:
    response = _create(client, dateIso="sometime last week")
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


# --- checkout -------------------------------------------------------------


def test_checkout_requires_an_idempotency_key(client) -> None:
    letter_id = _create(client).json()["id"]
    response = client.post(f"/api/v1/letters/{letter_id}/checkout", json={})
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "idempotency_required"


def test_checkout_with_the_same_key_returns_the_same_session(client) -> None:
    letter_id = _create(client).json()["id"]
    headers = {"Idempotency-Key": "abc-123"}
    first = client.post(f"/api/v1/letters/{letter_id}/checkout", json={}, headers=headers)
    second = client.post(f"/api/v1/letters/{letter_id}/checkout", json={}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_checkout_on_an_unknown_letter_is_a_404(client) -> None:
    response = client.post(
        "/api/v1/letters/ltr_nope/checkout", json={}, headers={"Idempotency-Key": "k"}
    )
    assert response.status_code == 404


# --- status ---------------------------------------------------------------


def test_status_never_claims_delivery(client) -> None:
    letter_id = _create(client).json()["id"]
    body = client.get(f"/api/v1/letters/{letter_id}/status").json()
    assert body["status"] == "draft"
    assert "deliver" not in body["statusLabel"].lower()


def test_status_labels_distinguish_submitted_from_delivered(client) -> None:
    from app.api.routes import STATUS_LABELS

    assert STATUS_LABELS["submitted"] == "Submitted to the mailing provider"
    assert not any("delivered" in label.lower() for label in STATUS_LABELS.values())


# --- webhooks -------------------------------------------------------------


def test_a_payment_webhook_marks_the_letter_paid_and_triggers_the_mailing(client) -> None:
    letter_id = _create(client).json()["id"]
    with SessionLocal() as db:
        quoted = db.get(Letter, letter_id).quoted_cents

    response = client.post(
        "/api/v1/webhooks/payments",
        content=json.dumps(
            {
                "id": "evt_api_1",
                "kind": "paid",
                "letter_id": letter_id,
                "session_id": "cs_1",
                "payment_reference": "pi_1",
                "amount_cents": quoted,
            }
        ),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200

    with SessionLocal() as db:
        letter = db.get(Letter, letter_id)
        # The background task runs on response close in TestClient.
        assert letter.status in {LetterStatus.PAID.value, LetterStatus.SUBMITTED.value}


def test_a_replayed_payment_webhook_is_accepted_but_not_processed_twice(client) -> None:
    letter_id = _create(client).json()["id"]
    with SessionLocal() as db:
        quoted = db.get(Letter, letter_id).quoted_cents

    body = json.dumps(
        {
            "id": "evt_dupe",
            "kind": "paid",
            "letter_id": letter_id,
            "payment_reference": "pi_1",
            "amount_cents": quoted,
        }
    )
    headers = {"Content-Type": "application/json"}
    first = client.post("/api/v1/webhooks/payments", content=body, headers=headers)
    second = client.post("/api/v1/webhooks/payments", content=body, headers=headers)

    assert first.status_code == second.status_code == 200
    with SessionLocal() as db:
        from app.db.models import WebhookEvent

        events = (
            db.execute(select(WebhookEvent).where(WebhookEvent.event_id == "evt_dupe"))
            .scalars()
            .all()
        )
        assert len(events) == 1


def test_a_malformed_webhook_body_is_a_400_not_a_500(client) -> None:
    response = client.post(
        "/api/v1/webhooks/payments",
        content="not json at all",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400


def test_a_webhook_for_an_unknown_letter_is_accepted_and_ignored(client) -> None:
    """Providers retry non-200s; an event we cannot match is not an error."""
    response = client.post(
        "/api/v1/webhooks/payments",
        content=json.dumps({"id": "evt_orphan", "kind": "paid", "letter_id": "ltr_nope"}),
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 200


# --- suppression ----------------------------------------------------------


def test_anyone_can_add_an_address_to_the_do_not_mail_list(client) -> None:
    response = client.post(
        "/api/v1/suppressions", json={"address": ADDRESS, "reason": "please stop"}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_there_is_no_endpoint_that_removes_a_suppression(client) -> None:
    """Un-suppressing from the public site would defeat the point."""
    routes = {
        (route.path, method)
        for route in client.app.routes
        for method in getattr(route, "methods", set())
    }
    assert not any(
        "suppression" in path and method in {"DELETE", "PUT", "PATCH"} for path, method in routes
    )


# --- CORS and headers -----------------------------------------------------


def test_cors_allows_the_configured_origin_only(client) -> None:
    allowed = client.options(
        "/api/v1/letters",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    denied = client.options(
        "/api/v1/letters",
        headers={
            "Origin": "https://evil.example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert denied.headers.get("access-control-allow-origin") is None


def test_credentials_are_not_allowed_across_origins(client) -> None:
    response = client.options(
        "/api/v1/letters",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
    )
    assert response.headers.get("access-control-allow-credentials") is None


# --- demo safety ----------------------------------------------------------


def test_nothing_in_this_configuration_can_send_real_mail(client) -> None:
    from app.providers.factory import get_providers

    mail, payments = get_providers()
    assert mail.can_send_real_mail is False
    assert payments.can_charge_real_money is False


def test_a_live_deployment_wired_to_the_mock_refuses_to_start() -> None:
    from pydantic import ValidationError

    from app.core.config import Settings
    from app.providers.factory import ConfigurationError, build_mail_provider

    # The refusal may fire at config-load time (a Settings validator) or when the
    # provider is built; either is "refuses to start".
    with pytest.raises((ConfigurationError, ValidationError)):
        settings = Settings(
            app_mode="live",
            mail_provider="mock",
            address_pepper="a-real-pepper-value",
            postgrid_api_key="live_sk_x",
            postgrid_webhook_secret="s",
            return_line1="1 Main",
            return_city="Marfa",
            return_state="TX",
            return_zip="79843",
        )
        build_mail_provider(settings)


def test_a_configuration_that_charges_but_cannot_mail_refuses_to_start() -> None:
    from app.core.config import Settings
    from app.payments.stripe_provider import StripePaymentProvider
    from app.providers.factory import ConfigurationError, assert_consistent
    from app.providers.mock import MockMailProvider

    settings = Settings(app_mode="demo", address_pepper="a-real-pepper-value")
    with pytest.raises(ConfigurationError):
        assert_consistent(
            MockMailProvider(), StripePaymentProvider("sk_live_x", "whsec_x"), settings
        )


def test_a_live_postgrid_key_is_refused_unless_explicitly_allowed() -> None:
    from app.providers.postgrid import PostGridMailProvider

    with pytest.raises(ValueError, match="Refusing a live PostGrid key"):
        PostGridMailProvider("live_sk_abc", "whsec", allow_live_key=False)


def test_cors_wildcards_are_rejected_at_startup() -> None:
    from app.core.config import Settings

    with pytest.raises(ValueError, match="exact origins"):
        Settings(cors_allow_origins="*")
