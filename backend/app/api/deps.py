"""Shared dependencies: settings, providers, client identity, rate limits, bots."""

from __future__ import annotations

import logging

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.ratelimit import check_and_consume
from app.core.security import hash_client_ip
from app.db.session import get_db
from app.payments.base import PaymentProvider
from app.providers.base import MailProvider
from app.providers.factory import get_providers

log = logging.getLogger(__name__)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def settings_dep() -> Settings:
    return get_settings()


def mail_provider_dep() -> MailProvider:
    return get_providers()[0]


def payment_provider_dep() -> PaymentProvider | None:
    return get_providers()[1]


def client_ip(request: Request) -> str:
    """The caller's IP, preferring the proxy header the platform actually sets.

    Only the first hop is used, and only when the app is behind a proxy that
    sets it. It is hashed immediately afterwards; nothing stores the raw value.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    # A placeholder identifier for rate-limiting when the client is unknown, not
    # a socket bind address.
    return request.client.host if request.client else "0.0.0.0"  # noqa: S104


def client_hash(request: Request, settings: Settings = Depends(settings_dep)) -> str:
    return hash_client_ip(client_ip(request), settings.address_pepper)


def rate_limit(bucket: str, limit_attr: str, window_seconds: int):
    """Builds a dependency that consumes one token from a named bucket."""

    def dependency(
        db: Session = Depends(get_db),
        settings: Settings = Depends(settings_dep),
        hashed: str = Depends(client_hash),
    ) -> None:
        limit = getattr(settings, limit_attr)
        result = check_and_consume(db, f"{bucket}:{hashed}", limit, window_seconds)
        db.commit()
        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "rate_limited",
                    "detail": (
                        "That is more requests than this service accepts in one go. "
                        "Please try again shortly."
                    ),
                },
                headers={"Retry-After": str(result.retry_after_seconds)},
            )

    return dependency


def verify_bot_token(token: str | None, settings: Settings) -> None:
    """Cloudflare Turnstile, when configured.

    Absent configuration this is a no-op: bot protection is required for live
    purchases, which the purchase route enforces separately, and demanding a
    token in demo or self-print flows would only be friction.
    """
    if not settings.turnstile_secret_key:
        return
    if not token:
        raise HTTPException(
            status_code=400,
            detail={"code": "bot_check_required", "detail": "Please complete the human check."},
        )
    try:
        response = httpx.post(
            TURNSTILE_VERIFY_URL,
            data={"secret": settings.turnstile_secret_key, "response": token},
            timeout=8.0,
        )
        ok = bool(response.json().get("success"))
    except Exception as exc:
        log.error("turnstile verification error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={"code": "bot_check_unavailable", "detail": "The human check is unavailable."},
        ) from exc

    if not ok:
        raise HTTPException(
            status_code=400,
            detail={"code": "bot_check_failed", "detail": "The human check did not pass."},
        )
