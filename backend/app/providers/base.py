"""The mailing-provider interface.

Everything the rest of the app knows about printing and posting is in this
file. A provider must be able to do four things: check an address, print and
post a letter idempotently, tell us what its webhook events mean, and say
whether it is capable of sending real mail at all.

That last one is not decoration. `can_send_real_mail` is what the demo-safety
test asserts against, and what the startup check uses to refuse a live
deployment wired to the mock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Protocol, runtime_checkable

from app.letters.address import UsAddress


class Deliverability(StrEnum):
    DELIVERABLE = "deliverable"
    DELIVERABLE_WITH_CHANGES = "deliverable_with_changes"
    NEEDS_UNIT = "needs_unit"
    UNDELIVERABLE = "undeliverable"


@dataclass(frozen=True, slots=True)
class AddressVerification:
    status: Deliverability
    message: str
    standardized: UsAddress | None
    provider: str

    @property
    def usable(self) -> bool:
        return self.status is not Deliverability.UNDELIVERABLE


@dataclass(frozen=True, slots=True)
class SendLetterRequest:
    #: Our own letter id. Used as the provider idempotency key, so a retry of a
    #: submission for the same letter can never produce a second envelope.
    idempotency_key: str
    to_address: UsAddress
    from_address: UsAddress
    from_name: str
    html: str
    description: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SendLetterResult:
    provider: str
    provider_id: str
    expected_delivery_date: date | None
    #: True when the provider recognised the idempotency key and returned the
    #: letter it already created, rather than creating a new one.
    deduplicated: bool = False


@dataclass(frozen=True, slots=True)
class ProviderEvent:
    provider: str
    event_id: str
    event_type: str
    provider_letter_id: str | None
    occurred_at: str | None
    raw: dict


class MailProviderError(Exception):
    """A provider call failed. `retryable` decides refund versus retry."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


@runtime_checkable
class MailProvider(Protocol):
    name: str

    @property
    def can_send_real_mail(self) -> bool:
        """False for anything that only pretends. Never a configuration value."""
        ...

    def verify_address(self, address: UsAddress) -> AddressVerification: ...

    def send_letter(self, request: SendLetterRequest) -> SendLetterResult: ...

    def parse_webhook(self, headers: dict[str, str], body: bytes) -> ProviderEvent:
        """Verify the signature and return the event. Raises on any doubt."""
        ...
