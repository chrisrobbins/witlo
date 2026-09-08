"""Settings.

Every secret arrives through the environment. The app refuses to start in live
mode without the credentials that mode requires, rather than starting and
failing at the moment someone tries to pay — a half-configured mailing service
is worse than one that is plainly off.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppMode = Literal["demo", "live"]
MailProviderName = Literal["mock", "postgrid"]
PaymentProviderName = Literal["none", "mock", "stripe"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False
    )

    # --- Application ------------------------------------------------------
    app_mode: AppMode = "demo"
    app_name: str = "Why Is This Light On?"
    public_site_url: str = "https://witlo.info"
    contact_email: str = "hello@witlo.info"
    log_level: str = "INFO"

    # --- Database ---------------------------------------------------------
    # SQLite is fine for local development; production should be PostgreSQL.
    database_url: str = "sqlite+pysqlite:///./wittl.db"

    # --- CORS -------------------------------------------------------------
    # Comma-separated exact origins. No wildcards: this API accepts writes.
    cors_allow_origins: str = "http://localhost:5173"

    # --- Secrets ----------------------------------------------------------
    # Used to HMAC recipient addresses. Changing it orphans every existing
    # cooldown and suppression record, so treat it as permanent.
    address_pepper: str = Field(default="dev-only-pepper-change-me", min_length=8)

    # --- Mailing ----------------------------------------------------------
    mail_provider: MailProviderName = "mock"
    # PostGrid issues separate keys for Print & Mail and Address Verification.
    # Leave the AV key blank to reuse the Print & Mail key.
    postgrid_api_key: str = ""
    postgrid_av_api_key: str = ""
    postgrid_webhook_secret: str = ""
    postgrid_use_test_key_only: bool = True
    # The return address printed on the envelope. Never the sender's.
    return_name: str = "Why Is This Light On?"
    return_line1: str = ""
    return_line2: str = ""
    return_city: str = ""
    return_state: str = ""
    return_zip: str = ""

    # --- Payments ---------------------------------------------------------
    payment_provider: PaymentProviderName = "none"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    checkout_success_url: str = "https://witlo.info/#/receipt?letter={LETTER_ID}"
    checkout_cancel_url: str = "https://witlo.info/#/create"

    # --- Pricing (server-side authority) ----------------------------------
    price_postage_cents: int = 174
    price_printing_cents: int = 95
    price_service_cents: int = 80
    price_currency: str = "usd"

    # --- Policy -----------------------------------------------------------
    repeat_address_cooldown_days: int = 180
    rate_limit_per_ip_per_hour: int = 12
    rate_limit_drafts_per_ip_per_day: int = 30
    retention_days: int = 90
    max_letters_per_address_lifetime: int = 3

    # --- Bot protection (optional) ----------------------------------------
    turnstile_secret_key: str = ""

    # --- Internal ops (optional) ----------------------------------------
    # Bearer token for the /api/v1/internal/* routes (the retry, purge and
    # migrate jobs a scheduler calls). Blank disables the whole router.
    cron_secret: str = ""

    @field_validator("cors_allow_origins")
    @classmethod
    def _no_wildcard(cls, value: str) -> str:
        if "*" in value:
            raise ValueError("CORS_ALLOW_ORIGINS must list exact origins; this API accepts writes.")
        return value

    @model_validator(mode="after")
    def _live_mode_requires_credentials(self) -> Settings:
        if self.app_mode != "live":
            return self

        problems: list[str] = []
        if self.mail_provider == "mock":
            problems.append("APP_MODE=live with MAIL_PROVIDER=mock would never mail anything")
        if self.mail_provider == "postgrid":
            if not self.postgrid_api_key:
                problems.append("POSTGRID_API_KEY is required")
            if not self.postgrid_webhook_secret:
                problems.append("POSTGRID_WEBHOOK_SECRET is required")
            if not (
                self.return_line1 and self.return_city and self.return_state and self.return_zip
            ):
                problems.append("a complete RETURN_* address is required")
        if self.payment_provider == "stripe":
            if not self.stripe_secret_key:
                problems.append("STRIPE_SECRET_KEY is required")
            if not self.stripe_webhook_secret:
                problems.append("STRIPE_WEBHOOK_SECRET is required")
        if self.address_pepper == "dev-only-pepper-change-me":
            problems.append("ADDRESS_PEPPER must be changed from the default")

        if problems:
            raise ValueError("Refusing to start in live mode:\n  - " + "\n  - ".join(problems))
        return self

    # --- Derived ----------------------------------------------------------
    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_demo(self) -> bool:
        return self.app_mode == "demo"

    @property
    def payments_enabled(self) -> bool:
        return self.payment_provider != "none"

    @property
    def total_price_cents(self) -> int:
        return self.price_postage_cents + self.price_printing_cents + self.price_service_cents

    @property
    def uses_live_postgrid_key(self) -> bool:
        return self.postgrid_api_key.startswith("live_")

    @property
    def uses_live_stripe_key(self) -> bool:
        return self.stripe_secret_key.startswith("sk_live_")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
