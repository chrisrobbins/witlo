"""PostGrid mailing provider.

Chosen because it does the three things this service needs and takes them from a
self-serve account with a personal email: US first-class letters from a rendered
HTML document, USPS address verification, and signed delivery-status webhooks.

Endpoints and semantics used here:

  * `POST https://api.postgrid.com/print-mail/v1/letters` — print and post, with
    an `Idempotency-Key` header that makes a retried submission return the letter
    PostGrid already created instead of a second one
  * address verification: `POST https://api.postgrid.com/v1/addver/verifications`
    when a dedicated Address Verification key is configured, otherwise a
    `POST .../print-mail/v1/contacts` whose `addressStatus` carries the same
    verified/corrected/failed result on the Print & Mail key alone
  * webhooks signed as `PostGrid-Signature: t=<unix>,v1=<hex>`, an HMAC-SHA256
    over `"{t}.{raw body}"`. The webhook must be created with the **JSON** payload
    format, not PostGrid's JWT default.

Auth is the `x-api-key` header. Keys are `test_sk_…` in the sandbox and
`live_sk_…` in production; the sandbox creates letters and contacts but never
prints them and marks every address `verified`. A live key is refused unless the
deployment explicitly allows one, and every request carries a timeout so a
hanging provider cannot pin a worker.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import httpx

from app.core.security import SignatureError, verify_postgrid_signature
from app.letters.address import UsAddress

from .base import (
    AddressVerification,
    Deliverability,
    MailProviderError,
    ProviderEvent,
    SendLetterRequest,
    SendLetterResult,
)

MAIL_ROOT = "https://api.postgrid.com/print-mail/v1"
AV_ROOT = "https://api.postgrid.com/v1/addver"
TIMEOUT = httpx.Timeout(20.0, connect=8.0)

#: PostGrid's address `status` / `addressStatus` values, mapped onto ours. A
#: `corrected` result becomes NEEDS_UNIT when the correction it needed was a
#: missing or wrong secondary unit; see `_needs_unit`.
DELIVERABILITY_MAP = {
    "verified": Deliverability.DELIVERABLE,
    "corrected": Deliverability.DELIVERABLE_WITH_CHANGES,
    "failed": Deliverability.UNDELIVERABLE,
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

#: Substrings in a verification error that mean "the unit number is the problem".
_UNIT_HINTS = ("unit", "suite", "secondary", "apartment", "apt", "ste ")


class PostGridMailProvider:
    name = "postgrid"

    def __init__(
        self,
        api_key: str,
        webhook_secret: str,
        *,
        av_api_key: str | None = None,
        allow_live_key: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("A PostGrid API key is required.")
        if api_key.startswith("live_") and not allow_live_key:
            raise ValueError(
                "Refusing a live PostGrid key: set POSTGRID_USE_TEST_KEY_ONLY=false to send "
                "real mail."
            )
        self._api_key = api_key
        # PostGrid's Address Verification is a separate product with its own key
        # (`/v1/addver`). When one isn't configured, `verify_address` falls back
        # to creating a Print & Mail contact and reading its `addressStatus` —
        # which is what the Print & Mail key can do, and is real verification on
        # a live key (the sandbox marks everything `verified`).
        self._av_api_key = av_api_key or None
        self._webhook_secret = webhook_secret
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def can_send_real_mail(self) -> bool:
        return self._api_key.startswith("live_")

    # --- plumbing -------------------------------------------------------------

    def _post(
        self,
        root: str,
        path: str,
        payload: dict[str, Any],
        *,
        api_key: str,
        extra_headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        headers = {"x-api-key": api_key, "Content-Type": "application/json"}
        headers.update(extra_headers or {})
        try:
            response = self._client.post(f"{root}{path}", json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise MailProviderError(
                f"Could not reach the mailing provider: {exc}", retryable=True
            ) from exc

        if response.status_code >= 500 or response.status_code == 429:
            raise MailProviderError(
                f"The mailing provider returned {response.status_code}.", retryable=True
            )
        if response.status_code >= 400:
            raise MailProviderError(
                f"The mailing provider rejected the request: {_error_message(response)}",
                retryable=False,
            )
        return response

    # --- addresses ---------------------------------------------------------

    def verify_address(self, address: UsAddress) -> AddressVerification:
        if self._av_api_key:
            raw_status, fields, errors = self._verify_via_av_api(address)
        else:
            raw_status, fields, errors = self._verify_via_contact(address)

        status = DELIVERABILITY_MAP.get(raw_status, Deliverability.UNDELIVERABLE)
        if status is Deliverability.DELIVERABLE_WITH_CHANGES and _needs_unit(errors):
            status = Deliverability.NEEDS_UNIT

        standardized: UsAddress | None = None
        if status is not Deliverability.UNDELIVERABLE:
            standardized = UsAddress(
                line1=str(fields.get("line1") or address.line1),
                line2=str(fields.get("line2") or ""),
                city=str(fields.get("city") or address.city),
                state=str(fields.get("state") or address.state),
                zip=str(fields.get("zip") or address.zip)[:5],
            )

        return AddressVerification(
            status=status,
            message=MESSAGES[status],
            standardized=standardized,
            provider=self.name,
        )

    def _verify_via_av_api(self, address: UsAddress) -> tuple[str, dict[str, str], Any]:
        """The dedicated Address Verification product (`/v1/addver`)."""
        payload = {
            "address": {
                k: v
                for k, v in {
                    "line1": address.line1,
                    "line2": address.line2,
                    "city": address.city,
                    "state": address.state,
                    "zipCode": address.zip,
                    "country": "US",
                }.items()
                if v
            }
        }
        assert self._av_api_key is not None
        response = self._post(AV_ROOT, "/verifications", payload, api_key=self._av_api_key)
        data = response.json().get("data") or {}
        return (
            str(data.get("status", "failed")).lower(),
            {
                "line1": data.get("line1"),
                "line2": data.get("line2"),
                "city": data.get("city"),
                "state": data.get("state"),
                "zip": data.get("zipCode"),
            },
            data.get("errors"),
        )

    def _verify_via_contact(self, address: UsAddress) -> tuple[str, dict[str, str], Any]:
        """Fallback: a Print & Mail contact carries an `addressStatus` and the
        standardised fields. Real verification on a live key; the sandbox marks
        everything `verified`."""
        payload = {
            "firstName": "Resident",
            "addressLine1": address.line1,
            "city": address.city,
            "provinceOrState": address.state,
            "postalOrZip": address.zip,
            "country": "US",
        }
        if address.line2:
            payload["addressLine2"] = address.line2
        c = self._post(MAIL_ROOT, "/contacts", payload, api_key=self._api_key).json()
        return (
            str(c.get("addressStatus", "failed")).lower(),
            {
                "line1": c.get("addressLine1"),
                "line2": c.get("addressLine2"),
                "city": c.get("city"),
                "state": c.get("provinceOrState"),
                "zip": c.get("postalOrZip"),
            },
            c.get("addressErrors") or c.get("errors"),
        )

    # --- sending ---------------------------------------------------------

    def send_letter(self, request: SendLetterRequest) -> SendLetterResult:
        payload: dict[str, Any] = {
            "description": request.description[:255],
            "to": {
                "firstName": "Current",
                "lastName": "Resident",
                "addressLine1": request.to_address.line1,
                "city": request.to_address.city,
                "provinceOrState": request.to_address.state,
                "postalOrZip": request.to_address.zip,
                "country": "US",
            },
            "from": {
                "companyName": request.from_name,
                "addressLine1": request.from_address.line1,
                "city": request.from_address.city,
                "provinceOrState": request.from_address.state,
                "postalOrZip": request.from_address.zip,
                "country": "US",
            },
            "html": request.html,
            "color": False,
            "doubleSided": False,
            "express": False,
            "addressPlacement": "top_first_page",
        }
        if request.to_address.line2:
            payload["to"]["addressLine2"] = request.to_address.line2
        if request.from_address.line2:
            payload["from"]["addressLine2"] = request.from_address.line2
        if request.metadata:
            payload["metadata"] = dict(request.metadata)

        response = self._post(
            MAIL_ROOT,
            "/letters",
            payload,
            api_key=self._api_key,
            extra_headers={"Idempotency-Key": request.idempotency_key[:256]},
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
            expected_delivery_date=_parse_date(body.get("expectedDeliveryDate")),
            # PostGrid does not expose a replay indicator; the unique constraint
            # on `provider_letter_id` is what actually stops a second envelope.
            deduplicated=False,
        )

    # --- webhooks ---------------------------------------------------------

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> ProviderEvent:
        lower = {k.lower(): v for k, v in headers.items()}
        try:
            verify_postgrid_signature(
                body, lower.get("postgrid-signature", ""), self._webhook_secret
            )
        except SignatureError as exc:
            raise MailProviderError(str(exc), retryable=False) from exc

        text = body.decode("utf-8")
        if not text.lstrip().startswith("{"):
            # PostGrid webhooks default to a signed JWT body; this integration
            # needs the JSON format, chosen when the webhook is created.
            raise MailProviderError(
                "PostGrid webhook is not JSON. Recreate it with the JSON payload format.",
                retryable=False,
            )
        payload = json.loads(text)

        raw_type = str(payload.get("type") or "")
        data = payload.get("data") or {}
        # PostGrid sends one `letter.updated` for every status change and puts the
        # real state in `data.status` / `data.imbStatus`. Synthesise the granular
        # event names the state map keys on.
        imb = str(data.get("imbStatus") or "")
        letter_status = str(data.get("status") or "")
        if raw_type == "letter.updated" and (imb or letter_status):
            event_type = f"letter.{imb or letter_status}"
        else:
            event_type = raw_type

        return ProviderEvent(
            provider=self.name,
            event_id=str(payload.get("id", "")),
            event_type=event_type,
            provider_letter_id=str(data.get("id")) if data.get("id") else None,
            occurred_at=payload.get("createdAt") or data.get("updatedAt"),
            raw=payload,
        )


def _needs_unit(errors: Any) -> bool:
    """True when a verification error is about the secondary (unit) line."""
    text = json.dumps(errors).lower() if errors else ""
    return any(hint in text for hint in _UNIT_HINTS)


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
        body = response.json()
    except ValueError:
        return response.text[:300]
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict) and error.get("message"):
            return str(error["message"])[:300]
        if body.get("message"):
            return str(body["message"])[:300]
    return response.text[:300]
