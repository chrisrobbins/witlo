"""US address normalization and hashing.

`normalize_address_key` must stay byte-identical to
`frontend/src/lib/address.ts::normalizeAddressKey`; `tests/test_address.py` and
the frontend's `tests/address.test.ts` run the same fixture table.

The hash is what the cooldown and the do-not-mail list are keyed on. It is an
HMAC rather than a bare digest so that a leaked database cannot be brute-forced
back into a list of addresses — the space of US addresses is small enough to
enumerate, and a plain SHA-256 of one would be reversible in an afternoon.
"""

from __future__ import annotations

import hmac
import re
from dataclasses import dataclass
from hashlib import sha256

_NON_ALNUM = re.compile(r"[^A-Z0-9]+")

US_STATE_CODES = frozenset(
    """AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT
    NE NV NH NJ NM NY NC ND OH OK OR PA PR RI SC SD TN TX UT VT VA WA WV WI WY
    AS GU MP VI AA AE AP""".split()
)

_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")
_PO_BOX_RE = re.compile(r"\b(p\.?\s?o\.?\s?box|post\s+office\s+box)\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class UsAddress:
    line1: str
    line2: str
    city: str
    state: str
    zip: str

    def normalized(self) -> "UsAddress":
        return UsAddress(
            line1=" ".join(self.line1.split()),
            line2=" ".join(self.line2.split()),
            city=" ".join(self.city.split()),
            state=self.state.strip().upper()[:2],
            zip=self.zip.strip(),
        )

    def lines(self) -> list[str]:
        """The address block as printed, top to bottom."""
        out = [self.line1.strip()]
        if self.line2.strip():
            out.append(self.line2.strip())
        out.append(f"{self.city.strip()}, {self.state.strip().upper()} {self.zip.strip()}")
        return [line for line in out if line]


def _squash(value: str) -> str:
    return _NON_ALNUM.sub(" ", value.upper()).strip()


def normalize_address_key(address: UsAddress) -> str:
    """A stable "same mailbox" key. Mirrors the TypeScript implementation."""
    zip5 = _squash(address.zip).replace(" ", "")[:5]
    return "|".join(
        (
            _squash(address.line1),
            _squash(address.line2),
            _squash(address.city),
            _squash(address.state)[:2],
            zip5,
        )
    )


def address_hash(address: UsAddress, pepper: str) -> str:
    """HMAC-SHA256 of the normalized key. Hex, 64 chars."""
    return hmac.new(
        pepper.encode("utf-8"),
        normalize_address_key(address).encode("utf-8"),
        sha256,
    ).hexdigest()


class AddressError(ValueError):
    """Raised when an address cannot be used, with a message safe to show a user."""


def validate_us_address(address: UsAddress) -> UsAddress:
    """Server-side validation. Never trusts the client's checks."""
    a = address.normalized()

    if not a.line1:
        raise AddressError("A street address is required.")
    if len(a.line1) > 80:
        raise AddressError("The street address is too long for an envelope.")
    if not any(ch.isdigit() for ch in a.line1):
        raise AddressError("A US street address usually starts with a number.")
    if _PO_BOX_RE.search(a.line1) or _PO_BOX_RE.search(a.line2):
        raise AddressError("A PO box has no outdoor light. Please use the street address.")
    if len(a.line2) > 60:
        raise AddressError("The unit line is too long.")
    if not a.city or len(a.city) > 50:
        raise AddressError("A city is required.")
    if a.state not in US_STATE_CODES:
        raise AddressError("Please choose a US state or territory.")
    if not _ZIP_RE.match(a.zip):
        raise AddressError("Please enter a ZIP code as 12345 or 12345-6789.")

    return a
