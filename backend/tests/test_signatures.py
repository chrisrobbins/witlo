"""Webhook signature verification.

This is the boundary where an attacker who can reach the API tries to convince
it that money arrived, or that a letter was delivered. Every one of these tests
describes an attack that must fail.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from app.core.security import (
    SignatureError,
    verify_postgrid_signature,
    verify_stripe_signature,
)

SECRET = "whsec_test_secret"
BODY = b'{"id":"evt_1","type":"checkout.session.completed"}'


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    return hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()


def _rejects(fn, *args, **kwargs) -> str:
    try:
        fn(*args, **kwargs)
    except SignatureError as exc:
        return str(exc)
    raise AssertionError("expected the signature check to fail")  # pragma: no cover


# --- Stripe ---------------------------------------------------------------


def test_stripe_accepts_a_correct_signature() -> None:
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={_sign(SECRET, ts, BODY)}"
    result = verify_stripe_signature(BODY, header, SECRET, now=now)
    assert result.provider == "stripe"
    assert result.body == BODY


def test_stripe_rejects_a_forged_signature() -> None:
    ts = str(int(time.time()))
    _rejects(verify_stripe_signature, BODY, f"t={ts},v1={'0' * 64}", SECRET)


def test_stripe_rejects_a_signature_made_with_a_different_secret() -> None:
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={_sign('whsec_wrong', ts, BODY)}"
    _rejects(verify_stripe_signature, BODY, header, SECRET, now=now)


def test_stripe_rejects_a_tampered_body() -> None:
    """The classic attack: a valid signature replayed over a different payload."""
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={_sign(SECRET, ts, BODY)}"
    tampered = BODY.replace(b"evt_1", b"evt_2")
    _rejects(verify_stripe_signature, tampered, header, SECRET, now=now)


def test_stripe_rejects_an_expired_timestamp() -> None:
    now = time.time()
    old = str(int(now) - 4000)
    header = f"t={old},v1={_sign(SECRET, old, BODY)}"
    message = _rejects(verify_stripe_signature, BODY, header, SECRET, now=now)
    assert "tolerance" in message


def test_stripe_rejects_a_future_timestamp_too() -> None:
    now = time.time()
    future = str(int(now) + 4000)
    header = f"t={future},v1={_sign(SECRET, future, BODY)}"
    _rejects(verify_stripe_signature, BODY, header, SECRET, now=now)


def test_stripe_ignores_the_v0_test_scheme() -> None:
    """v0 is Stripe's fake test scheme; honouring it would be a downgrade."""
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v0={_sign(SECRET, ts, BODY)}"
    _rejects(verify_stripe_signature, BODY, header, SECRET, now=now)


def test_stripe_accepts_any_valid_v1_during_a_secret_roll() -> None:
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={'a' * 64},v1={_sign(SECRET, ts, BODY)}"
    assert verify_stripe_signature(BODY, header, SECRET, now=now).timestamp == int(ts)


def test_stripe_rejects_missing_or_malformed_headers() -> None:
    _rejects(verify_stripe_signature, BODY, "", SECRET)
    _rejects(verify_stripe_signature, BODY, "nonsense", SECRET)
    _rejects(verify_stripe_signature, BODY, "t=abc,v1=deadbeef", SECRET)
    _rejects(verify_stripe_signature, BODY, f"v1={'0' * 64}", SECRET)


def test_stripe_rejects_when_no_secret_is_configured() -> None:
    ts = str(int(time.time()))
    _rejects(verify_stripe_signature, BODY, f"t={ts},v1={'0' * 64}", "")


def test_a_zero_tolerance_is_refused_rather_than_disabling_replay_checks() -> None:
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={_sign(SECRET, ts, BODY)}"
    message = _rejects(verify_stripe_signature, BODY, header, SECRET, tolerance=0, now=now)
    assert "replay" in message


# --- PostGrid -----------------------------------------------------------------


PG_BODY = b'{"id":"evt_pg","type":"letter.updated","data":{"id":"letter_1","status":"printing"}}'
PG_SECRET = "webhook_secret_pg"


def _pg_header(secret: str, ts: str, body: bytes) -> str:
    return f"t={ts},v1={_sign(secret, ts, body)}"


def test_postgrid_accepts_a_correct_signature() -> None:
    now = time.time()
    ts = str(int(now))
    header = _pg_header(PG_SECRET, ts, PG_BODY)
    result = verify_postgrid_signature(PG_BODY, header, PG_SECRET, now=now)
    assert result.provider == "postgrid"
    assert result.body == PG_BODY


def test_postgrid_rejects_a_forged_signature() -> None:
    ts = str(int(time.time()))
    _rejects(verify_postgrid_signature, PG_BODY, f"t={ts},v1={'0' * 64}", PG_SECRET)


def test_postgrid_rejects_a_signature_made_with_a_different_secret() -> None:
    now = time.time()
    ts = str(int(now))
    header = _pg_header("wrong_secret", ts, PG_BODY)
    _rejects(verify_postgrid_signature, PG_BODY, header, PG_SECRET, now=now)


def test_postgrid_rejects_a_tampered_body() -> None:
    now = time.time()
    ts = str(int(now))
    header = _pg_header(PG_SECRET, ts, PG_BODY)
    tampered = PG_BODY.replace(b"printing", b"returned_to_sender")
    _rejects(verify_postgrid_signature, tampered, header, PG_SECRET, now=now)


def test_postgrid_rejects_a_replayed_old_event() -> None:
    now = time.time()
    old = str(int(now) - 4000)
    header = _pg_header(PG_SECRET, old, PG_BODY)
    message = _rejects(verify_postgrid_signature, PG_BODY, header, PG_SECRET, now=now)
    assert "tolerance" in message


def test_postgrid_rejects_a_future_timestamp_too() -> None:
    now = time.time()
    future = str(int(now) + 4000)
    header = _pg_header(PG_SECRET, future, PG_BODY)
    _rejects(verify_postgrid_signature, PG_BODY, header, PG_SECRET, now=now)


def test_postgrid_accepts_any_valid_v1_during_a_secret_roll() -> None:
    now = time.time()
    ts = str(int(now))
    header = f"t={ts},v1={'a' * 64},v1={_sign(PG_SECRET, ts, PG_BODY)}"
    assert verify_postgrid_signature(PG_BODY, header, PG_SECRET, now=now).timestamp == int(ts)


def test_postgrid_rejects_missing_or_malformed_headers_and_missing_secret() -> None:
    now = time.time()
    ts = str(int(now))
    _rejects(verify_postgrid_signature, PG_BODY, "", PG_SECRET)
    _rejects(verify_postgrid_signature, PG_BODY, "nonsense", PG_SECRET)
    _rejects(verify_postgrid_signature, PG_BODY, "t=abc,v1=deadbeef", PG_SECRET, now=now)
    _rejects(verify_postgrid_signature, PG_BODY, f"v1={'0' * 64}", PG_SECRET)
    _rejects(verify_postgrid_signature, PG_BODY, _pg_header(PG_SECRET, ts, PG_BODY), "", now=now)


def test_the_mail_and_payment_secrets_do_not_cross_verify() -> None:
    """Same construction, but a payload signed with the mailing secret must not
    verify on the payment endpoint, which holds a different secret."""
    now = time.time()
    ts = str(int(now))
    header = _pg_header(PG_SECRET, ts, PG_BODY)
    _rejects(verify_stripe_signature, PG_BODY, header, SECRET, now=now)
