"""A deterministic mailing provider that cannot mail anything.

Same input, same output, every time and on every machine — no clock, no random
numbers, no network. That makes it usable as a test fixture and as the default
for local development, and it makes demo behaviour reproducible.

Test addresses, chosen so a developer can exercise every branch by hand:

  * ZIP 00000, or a street line containing "undeliverable"  -> undeliverable
  * a street line containing "needs unit"                    -> needs_unit
  * a ZIP+4, or stray whitespace anywhere                    -> deliverable_with_changes
  * a street line containing "provider down"                 -> a retryable failure
  * a street line containing "provider reject"               -> a permanent failure
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from app.letters.address import UsAddress, normalize_address_key

from .base import (
    AddressVerification,
    Deliverability,
    MailProviderError,
    ProviderEvent,
    SendLetterRequest,
    SendLetterResult,
)

#: A fixed epoch so "expected delivery" is stable across runs and machines.
_EPOCH = date(2026, 1, 1)


class MockMailProvider:
    name = "mock"

    @property
    def can_send_real_mail(self) -> bool:
        return False

    # --- addresses --------------------------------------------------------

    def verify_address(self, address: UsAddress) -> AddressVerification:
        haystack = f"{address.line1} {address.line2}".lower()
        zip5 = address.zip.strip()[:5]

        if zip5 == "00000" or "undeliverable" in haystack:
            return AddressVerification(
                status=Deliverability.UNDELIVERABLE,
                message=(
                    "The postal service does not recognise this address, so a letter would "
                    "come straight back. Please check the street number and ZIP."
                ),
                standardized=None,
                provider=self.name,
            )

        if "needs unit" in haystack:
            return AddressVerification(
                status=Deliverability.NEEDS_UNIT,
                message=(
                    "This building has multiple units and the postal service needs to know "
                    "which one. Please add an apartment or suite number."
                ),
                standardized=None,
                provider=self.name,
            )

        standardized = _standardize(address)
        if standardized != address.normalized():
            return AddressVerification(
                status=Deliverability.DELIVERABLE_WITH_CHANGES,
                message=(
                    "The postal service standardises addresses. We will use the version "
                    "shown here, which is the one that gets delivered."
                ),
                standardized=standardized,
                provider=self.name,
            )

        return AddressVerification(
            status=Deliverability.DELIVERABLE,
            message="The postal service recognises this address.",
            standardized=standardized,
            provider=self.name,
        )

    # --- sending ----------------------------------------------------------

    def send_letter(self, request: SendLetterRequest) -> SendLetterResult:
        haystack = f"{request.to_address.line1} {request.to_address.line2}".lower()
        if "provider down" in haystack:
            raise MailProviderError("The mailing provider is unavailable.", retryable=True)
        if "provider reject" in haystack:
            raise MailProviderError("The mailing provider refused this letter.", retryable=False)

        seed = hashlib.sha256(request.idempotency_key.encode("utf-8")).hexdigest()
        # Deterministic 4-8 business-day estimate derived from the key.
        offset = 4 + int(seed[:2], 16) % 5
        key = normalize_address_key(request.to_address)
        days = (int(hashlib.sha256(key.encode()).hexdigest()[:4], 16) % 400) + offset

        return SendLetterResult(
            provider=self.name,
            provider_id=f"ltr_mock_{seed[:16]}",
            expected_delivery_date=_EPOCH + timedelta(days=days),
            deduplicated=False,
        )

    # --- webhooks ---------------------------------------------------------

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> ProviderEvent:
        """Accepts an unsigned body — the mock is never reachable in live mode.

        `services.mailing` refuses to register a webhook route for a provider
        whose `can_send_real_mail` is False when APP_MODE is live, so this can
        only ever be called against a development deployment.
        """
        del headers
        payload = json.loads(body.decode("utf-8"))
        return ProviderEvent(
            provider=self.name,
            event_id=str(payload.get("id", "evt_mock")),
            event_type=str(payload.get("event_type", "letter.created")),
            provider_letter_id=payload.get("reference_id"),
            occurred_at=payload.get("date_created"),
            raw=payload,
        )


def _standardize(address: UsAddress) -> UsAddress:
    """A stand-in for USPS standardisation.

    Deliberately conservative: collapse whitespace, uppercase the state, drop a
    ZIP+4 down to five digits. Real standardisation also rewrites street
    suffixes and casing, but inventing those here would teach a developer to
    expect changes the real provider might not make.
    """
    a = address.normalized()
    return UsAddress(
        line1=a.line1,
        line2=a.line2,
        city=a.city,
        state=a.state.upper(),
        zip=a.zip.split("-")[0][:5],
    )
