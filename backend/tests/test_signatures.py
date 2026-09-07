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
    verify_lob_signature,
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


# --- Lob ------------------------------------------------------------------


LOB_BODY = b'{"id":"evt_lob","event_type":{"id":"letter.processed_for_delivery"}}'


def test_lob_accepts_a_correct_signature() -> None:
    now = time.time()
    ts_ms = str(int(now * 1000))
    signature = _sign(SECRET, ts_ms, LOB_BODY)
    result = verify_lob_signature(LOB_BODY, signature, ts_ms, SECRET, now=now)
    assert result.provider == "lob"


def test_lob_rejects_a_forged_signature() -> None:
    ts_ms = str(int(time.time() * 1000))
    _rejects(verify_lob_signature, LOB_BODY, "0" * 64, ts_ms, SECRET)


def test_lob_rejects_a_tampered_body() -> None:
    now = time.time()
    ts_ms = str(int(now * 1000))
    signature = _sign(SECRET, ts_ms, LOB_BODY)
    tampered = LOB_BODY.replace(b"processed_for_delivery", b"returned_to_sender")
    _rejects(verify_lob_signature, tampered, signature, ts_ms, SECRET, now=now)


def test_lob_rejects_a_replayed_old_event() -> None:
    now = time.time()
    old_ms = str(int((now - 3600) * 1000))
    signature = _sign(SECRET, old_ms, LOB_BODY)
    _rejects(verify_lob_signature, LOB_BODY, signature, old_ms, SECRET, now=now)


def test_lob_signs_the_timestamp_exactly_as_sent() -> None:
    """Reformatting the timestamp before hashing would break verification."""
    now = time.time()
    ts_ms = str(int(now * 1000))
    padded = ts_ms + "000"[:0]  # same string; the point is that we do not reformat
    signature = _sign(SECRET, padded, LOB_BODY)
    assert verify_lob_signature(LOB_BODY, signature, padded, SECRET, now=now)


def test_lob_rejects_missing_headers_and_missing_secret() -> None:
    ts_ms = str(int(time.time() * 1000))
    _rejects(verify_lob_signature, LOB_BODY, "", ts_ms, SECRET)
    _rejects(verify_lob_signature, LOB_BODY, "0" * 64, "", SECRET)
    _rejects(verify_lob_signature, LOB_BODY, "0" * 64, ts_ms, "")
    _rejects(verify_lob_signature, LOB_BODY, "0" * 64, "not-a-number", SECRET)


def test_the_two_schemes_do_not_accept_each_others_signatures() -> None:
    """A Lob-signed payload must not verify on the payment endpoint."""
    now = time.time()
    ts_ms = str(int(now * 1000))
    lob_signature = _sign(SECRET, ts_ms, LOB_BODY)
    _rejects(
        verify_stripe_signature,
        LOB_BODY,
        f"t={int(now)},v1={lob_signature}",
        SECRET,
        now=now,
    )
