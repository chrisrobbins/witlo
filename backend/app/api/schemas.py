"""Request and response models.

Field limits are set here as well as in the domain code. The domain checks are
the ones that matter; these exist so an oversized payload is rejected before it
is parsed into anything, and so the generated OpenAPI describes real limits.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.letters.address import UsAddress as DomainAddress
from app.letters.content import OBSERVATION_KEYS, SUGGESTION_KEYS, note_max_chars

_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")

ObservationKey = Literal["all_night", "upward", "spill", "unused_area", "other"]
SuggestionKey = Literal[
    "turn_off", "timer", "motion_sensor", "shield", "lower_brightness", "warmer_color"
]


class AddressIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    line1: str = Field(default="", max_length=80)
    line2: str = Field(default="", max_length=60)
    city: str = Field(default="", max_length=50)
    state: str = Field(default="", max_length=2)
    zip: str = Field(default="", max_length=10)

    def to_domain(self) -> DomainAddress:
        return DomainAddress(
            line1=self.line1, line2=self.line2, city=self.city, state=self.state, zip=self.zip
        )

    @classmethod
    def from_domain(cls, address: DomainAddress) -> AddressIn:
        return cls(
            line1=address.line1,
            line2=address.line2,
            city=address.city,
            state=address.state,
            zip=address.zip,
        )


class VerifyAddressRequest(BaseModel):
    address: AddressIn


class VerifyAddressResponse(BaseModel):
    status: Literal["deliverable", "deliverable_with_changes", "needs_unit", "undeliverable"]
    message: str
    standardized: AddressIn | None
    suppressed: bool
    cooldownUntil: str | None = None


class QuoteLineOut(BaseModel):
    label: str
    cents: int


class QuoteOut(BaseModel):
    currency: str
    totalCents: int
    lines: list[QuoteLineOut]
    deliveryEstimate: str
    disclaimer: str


class CreateLetterRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    address: AddressIn
    observations: list[ObservationKey] = Field(default_factory=list, max_length=5)
    note: str = Field(default="", max_length=1000)
    suggestions: list[SuggestionKey] = Field(default_factory=list, max_length=6)
    letterFingerprint: str = Field(default="", max_length=16)
    # The date the browser used to compose the letter it is asking us to print.
    # The sender approved a letter dated this day; if we recompose with a
    # different date the fingerprints will not match. Blank means "use ours".
    # The server still bounds it to its own date +/- one day (see create_draft).
    dateIso: str = Field(default="", max_length=10)
    senderEmail: EmailStr | None = None
    botToken: str | None = Field(default=None, max_length=4096)

    @field_validator("dateIso")
    @classmethod
    def _date_iso_shape(cls, value: str) -> str:
        if value and not _ISO_DATE.fullmatch(value):
            raise ValueError("dateIso must be YYYY-MM-DD.")
        return value

    @field_validator("observations", "suggestions")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        seen: list[str] = []
        for item in value:
            if item not in seen:
                seen.append(item)
        return seen

    @field_validator("note")
    @classmethod
    def _note_length(cls, value: str) -> str:
        # The composer truncates too; this makes an oversized note a validation
        # error rather than a silent trim of something the sender wrote.
        if len(value.strip()) > note_max_chars():
            raise ValueError(f"Please keep the note under {note_max_chars()} characters.")
        return value


class LetterOut(BaseModel):
    id: str
    status: str
    letterText: str
    letterFingerprint: str
    address: AddressIn
    quote: QuoteOut


class CheckoutOut(BaseModel):
    checkoutUrl: str
    draftId: str


class LetterStatusOut(BaseModel):
    id: str
    status: str
    statusLabel: str
    statusDetail: str
    submittedAt: str | None
    expectedDeliveryDate: str | None
    providerReference: str | None
    amountPaidCents: int | None


class SuppressionRequest(BaseModel):
    address: AddressIn
    reason: str = Field(default="", max_length=200)


class OkResponse(BaseModel):
    ok: bool = True


class ErrorResponse(BaseModel):
    code: str
    detail: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    mode: str
    mailProvider: str
    paymentProvider: str
    canSendRealMail: bool
    canChargeRealMoney: bool
    contentVersion: str


ALL_OBSERVATIONS = OBSERVATION_KEYS
ALL_SUGGESTIONS = SUGGESTION_KEYS
