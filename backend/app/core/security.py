"""Webhook signature verification and other small security primitives.

Both providers' schemes are implemented here directly rather than through their
SDKs, for three reasons: this is the boundary where an attacker can make us mail
letters or mark them paid, so it should be readable in full; it is verifiable
with unit tests that need no network and no vendor package; and it keeps the
security-critical code importable in environments where the SDKs are not
installed.

Stripe and PostGrid happen to use the same construction — HMAC-SHA256 over
`"{timestamp}.{raw_body}"`, with a `t=<unix>,v1=<hex>` header. They still get
one function each: each is bound to its own endpoint and its own webhook secret,
and a payload signed with the mailing secret must never verify on the payment
endpoint. A single "generic verifier" invites exactly that mistake.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

DEFAULT_TOLERANCE_SECONDS = 300


class SignatureError(Exception):
    """Raised when a webhook cannot be proven to come from the provider."""


@dataclass(frozen=True, slots=True)
class VerifiedWebhook:
    provider: str
    timestamp: int
    body: bytes


def _expected(secret: str, timestamp: str, body: bytes) -> str:
    message = timestamp.encode("utf-8") + b"." + body
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _check_timestamp(timestamp: int, tolerance: int, now: float | None) -> None:
    current = int(now if now is not None else time.time())
    if tolerance <= 0:
        raise SignatureError("A tolerance of zero disables replay protection.")
    if abs(current - timestamp) > tolerance:
        raise SignatureError("Webhook timestamp is outside the allowed tolerance.")


def verify_stripe_signature(
    body: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> VerifiedWebhook:
    """Verify a `Stripe-Signature` header.

    Format: `t=<unix>,v1=<hex>[,v1=<hex>...][,v0=<hex>]`. Only the `v1` scheme
    is accepted — `v0` is a test-only scheme and honouring it would be a
    downgrade. Multiple `v1` values appear while an endpoint secret is being
    rolled, and any one of them matching is enough.
    """
    if not secret:
        raise SignatureError("No Stripe webhook secret is configured.")
    if not signature_header:
        raise SignatureError("Missing Stripe-Signature header.")

    timestamp_raw: str | None = None
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp_raw = value
        elif key == "v1":
            signatures.append(value)

    if timestamp_raw is None or not signatures:
        raise SignatureError("Malformed Stripe-Signature header.")
    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise SignatureError("Malformed Stripe-Signature timestamp.") from exc

    expected = _expected(secret, timestamp_raw, body)
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise SignatureError("Stripe signature did not match.")

    _check_timestamp(timestamp, tolerance, now)
    return VerifiedWebhook(provider="stripe", timestamp=timestamp, body=body)


def verify_postgrid_signature(
    body: bytes,
    signature_header: str,
    secret: str,
    *,
    tolerance: int = DEFAULT_TOLERANCE_SECONDS,
    now: float | None = None,
) -> VerifiedWebhook:
    """Verify a `PostGrid-Signature` header.

    Format: `t=<unix seconds>,v1=<hex>`. The signed message is
    `"{t}.{raw body}"`. Multiple `v1` values can appear while a webhook secret is
    being rolled; any one matching is enough. Kept separate from the Stripe
    verifier — same maths, different secret, different endpoint.
    """
    if not secret:
        raise SignatureError("No PostGrid webhook secret is configured.")
    if not signature_header:
        raise SignatureError("Missing PostGrid-Signature header.")

    timestamp_raw: str | None = None
    signatures: list[str] = []
    for part in signature_header.split(","):
        key, _, value = part.strip().partition("=")
        if key == "t":
            timestamp_raw = value
        elif key == "v1":
            signatures.append(value)

    if timestamp_raw is None or not signatures:
        raise SignatureError("Malformed PostGrid-Signature header.")
    try:
        timestamp = int(timestamp_raw)
    except ValueError as exc:
        raise SignatureError("Malformed PostGrid-Signature timestamp.") from exc

    expected = _expected(secret, timestamp_raw, body)
    if not any(hmac.compare_digest(expected, candidate) for candidate in signatures):
        raise SignatureError("PostGrid signature did not match.")

    _check_timestamp(timestamp, tolerance, now)
    return VerifiedWebhook(provider="postgrid", timestamp=timestamp, body=body)


def digest(value: str) -> str:
    """A plain SHA-256 hex digest, for values that are not guessable."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_client_ip(ip: str, pepper: str) -> str:
    """Peppered, truncated hash of a client IP.

    Rate limiting needs to recognise a repeat visitor; it does not need to know
    where they live, and neither does anything reading the database later.
    """
    return hmac.new(pepper.encode("utf-8"), ip.encode("utf-8"), hashlib.sha256).hexdigest()[:32]


def new_token(nbytes: int = 16) -> str:
    return secrets.token_hex(nbytes)
