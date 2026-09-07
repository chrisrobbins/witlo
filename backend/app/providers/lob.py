"""Lob mailing provider.

Chosen because it does the three things this service needs from one vendor:
US first-class letters, USPS address verification, and signed delivery-status
webhooks. Endpoints and semantics used here:

  * `POST https://api.lob.com/v1/us_verifications` — address verification
  * `POST https://api.lob.com/v1/letters` — print and post, with an
    `Idempotency-Key` header (up to 256 characters) that makes a retried
    submission return the letter Lob already created instead of a second one
  * webhooks signed with `Lob-Signature` (HMAC-SHA256 hex) over
    `"{Lob-Signature-Timestamp}.{raw body}"`

Auth is HTTP Basic with the API key as the username and an empty password.

Two safety rails live in this class rather than in configuration: a live API key
is refused unless the deployment explicitly allows one, and every request
carries a timeout so a hanging provider cannot pin a worker.
"""

from __future__ import annotations

import base64
import json
from datetime import date, datetime
from typing import Any

import httpx

from app.core.security import SignatureError, verify_lob_signature
from app.letters.address import UsAddress

from .base import (
    AddressVerification,
    Deliverability,
    MailProviderError,
    ProviderEvent,
    SendLetterRequest,
    SendLetterResult,
)

API_ROOT = "https://api.lob.com/v1"
TIMEOUT = httpx.Timeout(20.0, connect=8.0)

#: Lob's `deliverability` values, mapped onto ours.
DELIVERABILITY_MAP = {
    "deliverable": Deliverability.DELIVERABLE,
    "deliverable_unnecessary_unit": Deliverability.DELIVERABLE_WITH_CHANGES,
    "deliverable_incorrect_unit": Deliverability.NEEDS_UNIT,
    "deliverable_missing_unit": Deliverability.NEEDS_UNIT,
    "undeliverable": Deliverability.UNDELIVERABLE,
}

MESSAGES = {
    Deliverability.DELIVERABLE: "The postal service recognises this address.",
    Deliverability.DELIVERABLE_WITH_CHANGES: (
        "The postal service standardises addresses. We will use the version shown here, "
        "which is the one that gets delivered."
    ),
    Deliverability.NEEDS_UNIT: (
        "This building has multiple units and the postal service needs to know which one. "
        "Please add or correct the apartment or suite number."
    ),
    Deliverability.UNDELIVERABLE: (
        "The postal service does not recognise this address, so a letter would come straight "
        "back. Please check the street number and ZIP."
    ),
}


class LobMailProvider:
    name = "lob"

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        *,
        allow_live_key: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("A Lob API key is required.")
        if api_key.startswith("live_") and not allow_live_key:
            raise ValueError(
                "Refusing a live Lob key: set LOB_USE_TEST_KEY_ONLY=false to send real mail."
            )
        self._api_key = api_key
        self._webhook_secret = webhook_secret
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def can_send_real_mail(self) -> bool:
        return self._api_key.startswith("live_")

    # --- plumbing ---------------------------------------------------------

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        token = base64.b64encode(f"{self._api_key}:".encode()).decode("ascii")
        headers = {"Authorization": f"Basic {token}", "Accept": "application/json"}
        headers.update(extra or {})
        return headers

    def _post(self, path: str, data: dict[str, Any], extra_headers: dict[str, str] | None = None):
        try:
            response = self._client.post(
                f"{API_ROOT}{path}", data=data, headers=self._headers(extra_headers)
            )
        except httpx.HTTPError as exc:
            raise MailProviderError(
                f"Could not reach the mailing provider: {exc}", retryable=True
            ) from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise MailProviderError(
                f"The mailing provider returned {response.status_code}.", retryable=True
            )
        if response.status_code >= 400:
            detail = _error_message(response)
            raise MailProviderError(
                f"The mailing provider rejected the request: {detail}", retryable=False
            )
        return response

    # --- addresses --------------------------------------------------------

    def verify_address(self, address: UsAddress) -> AddressVerification:
        payload = {
            "primary_line": address.line1,
            "secondary_line": address.line2,
            "city": address.city,
            "state": address.state,
            "zip_code": address.zip,
        }
        body = self._post("/us_verifications", {k: v for k, v in payload.items() if v}).json()

        raw_status = str(body.get("deliverability", "undeliverable"))
        status = DELIVERABILITY_MAP.get(raw_status, Deliverability.UNDELIVERABLE)
        components = body.get("components") or {}

        standardized: UsAddress | None = None
        if status is not Deliverability.UNDELIVERABLE:
            standardized = UsAddress(
                line1=str(body.get("primary_line") or address.line1),
                line2=str(body.get("secondary_line") or ""),
                city=str(components.get("city") or address.city),
                state=str(components.get("state") or address.state),
                zip=str(components.get("zip_code") or address.zip)[:5],
            )

        return AddressVerification(
            status=status,
            message=MESSAGES[status],
            standardized=standardized,
            provider=self.name,
        )

    # --- sending ----------------------------------------------------------

    def send_letter(self, request: SendLetterRequest) -> SendLetterResult:
        payload: dict[str, Any] = {
            "description": request.description[:255],
            "to[name]": "Current Resident",
            "to[address_line1]": request.to_address.line1,
            "to[address_city]": request.to_address.city,
            "to[address_state]": request.to_address.state,
            "to[address_zip]": request.to_address.zip,
            "from[name]": request.from_name,
            "from[address_line1]": request.from_address.line1,
            "from[address_city]": request.from_address.city,
            "from[address_state]": request.from_address.state,
            "from[address_zip]": request.from_address.zip,
            "file": request.html,
            "color": False,
            "double_sided": False,
            "address_placement": "top_first_page",
            "mail_type": "usps_first_class",
        }
        if request.to_address.line2:
            payload["to[address_line2]"] = request.to_address.line2
        if request.from_address.line2:
            payload["from[address_line2]"] = request.from_address.line2
        for key, value in request.metadata.items():
            payload[f"metadata[{key}]"] = value

        response = self._post(
            "/letters", payload, {"Idempotency-Key": request.idempotency_key[:256]}
        )
        body = response.json()

        provider_id = body.get("id")
        if not provider_id:
            raise MailProviderError(
                "The mailing provider did not return a letter id.", retryable=False
            )

        return SendLetterResult(
            provider=self.name,
            provider_id=str(provider_id),
            expected_delivery_date=_parse_date(body.get("expected_delivery_date")),
            # Lob replays the original response for a repeated idempotency key.
            deduplicated=response.headers.get("Idempotent-Replayed", "").lower() == "true",
        )

    # --- webhooks ---------------------------------------------------------

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> ProviderEvent:
        lower = {k.lower(): v for k, v in headers.items()}
        try:
            verify_lob_signature(
                body,
                lower.get("lob-signature", ""),
                lower.get("lob-signature-timestamp", ""),
                self._webhook_secret,
            )
        except SignatureError as exc:
            raise MailProviderError(str(exc), retryable=False) from exc

        payload = json.loads(body.decode("utf-8"))
        event_type = payload.get("event_type")
        # Lob nests the type: {"event_type": {"id": "letter.processed_for_delivery", ...}}
        type_id = event_type.get("id") if isinstance(event_type, dict) else event_type

        return ProviderEvent(
            provider=self.name,
            event_id=str(payload.get("id", "")),
            event_type=str(type_id or ""),
            provider_letter_id=payload.get("reference_id"),
            occurred_at=payload.get("date_created"),
            raw=payload,
        )


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", response.text))[:300]
    except Exception:
        return response.text[:300]
