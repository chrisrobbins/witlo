"""Chooses the mailing and payment providers, and refuses unsafe combinations.

The checks here run at startup, not at purchase time. A deployment that claims
to be live but is wired to a provider that cannot send mail is a deployment that
would take money and post nothing, so it should fail to boot.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.payments.base import PaymentProvider
from app.payments.mock import MockPaymentProvider
from app.providers.base import MailProvider
from app.providers.mock import MockMailProvider


class ConfigurationError(RuntimeError):
    pass


def build_mail_provider(settings: Settings) -> MailProvider:
    if settings.mail_provider == "mock":
        if settings.app_mode == "live":
            raise ConfigurationError(
                "APP_MODE=live with MAIL_PROVIDER=mock would accept payment and mail nothing."
            )
        return MockMailProvider()

    if settings.mail_provider == "lob":
        from app.providers.lob import LobMailProvider  # noqa: PLC0415

        return LobMailProvider(
            api_key=settings.lob_api_key,
            webhook_secret=settings.lob_webhook_secret,
            allow_live_key=not settings.lob_use_test_key_only,
        )

    raise ConfigurationError(f"Unknown MAIL_PROVIDER: {settings.mail_provider!r}")


def build_payment_provider(settings: Settings) -> PaymentProvider | None:
    if settings.payment_provider == "none":
        return None

    if settings.payment_provider == "mock":
        if settings.app_mode == "live":
            raise ConfigurationError(
                "APP_MODE=live with PAYMENT_PROVIDER=mock would mail letters nobody paid for."
            )
        return MockPaymentProvider()

    if settings.payment_provider == "stripe":
        from app.payments.stripe_provider import StripePaymentProvider  # noqa: PLC0415

        return StripePaymentProvider(
            secret_key=settings.stripe_secret_key,
            webhook_secret=settings.stripe_webhook_secret,
        )

    raise ConfigurationError(f"Unknown PAYMENT_PROVIDER: {settings.payment_provider!r}")


def assert_consistent(mail: MailProvider, payment: PaymentProvider | None, settings: Settings) -> None:
    """Cross-checks that no configuration can charge without being able to mail."""
    if settings.app_mode == "live" and not mail.can_send_real_mail:
        raise ConfigurationError(
            "APP_MODE=live but the mailing provider cannot send real mail "
            "(a test API key, or the mock)."
        )
    if payment is not None and payment.can_charge_real_money and not mail.can_send_real_mail:
        raise ConfigurationError(
            "Refusing to start: this configuration can charge real money but cannot "
            "send real mail."
        )
    if settings.app_mode != "live" and mail.can_send_real_mail:
        raise ConfigurationError(
            "Refusing to start: APP_MODE is not live but the mailing provider has a live key."
        )


@lru_cache(maxsize=1)
def get_providers() -> tuple[MailProvider, PaymentProvider | None]:
    settings = get_settings()
    mail = build_mail_provider(settings)
    payment = build_payment_provider(settings)
    assert_consistent(mail, payment, settings)
    return mail, payment
