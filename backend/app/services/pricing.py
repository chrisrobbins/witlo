"""Server-side pricing.

The browser is never asked what a letter costs; it displays whatever this
module returned. The quote is recomputed at checkout time and compared with the
amount stored on the draft, so a quote cannot be edited in flight.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuoteLine:
    label: str
    cents: int


@dataclass(frozen=True, slots=True)
class Quote:
    currency: str
    lines: tuple[QuoteLine, ...]
    total_cents: int
    delivery_estimate: str
    disclaimer: str


DELIVERY_ESTIMATE = (
    "Letters are handed to the postal service within one business day and typically arrive "
    "within four to eight business days. That is an estimate from the mailing provider, not "
    "a guarantee — first-class mail has no delivery confirmation."
)

DISCLAIMER = (
    "This price covers printing, postage and running the service, and it is the whole amount; "
    "there is nothing added later. If we take your payment and then cannot hand the letter to "
    "the mailing provider, we refund it in full without you asking."
)


def build_quote(
    *,
    postage_cents: int,
    printing_cents: int,
    service_cents: int,
    currency: str = "usd",
    pages: int = 1,
) -> Quote:
    """Compose the quote a sender sees.

    `pages` exists because the mailing provider charges per sheet and the
    longest possible letter — every observation, a full note, every suggestion —
    runs to two. The template bounds it there, so nothing beyond two is priced.
    """
    if pages < 1:
        raise ValueError("A letter has at least one page.")
    if pages > 2:
        raise ValueError("The template cannot produce more than two pages.")

    printing = printing_cents * pages
    lines = (
        QuoteLine("Printing and folding" + (" (2 pages)" if pages > 1 else ""), printing),
        QuoteLine("US first-class postage", postage_cents),
        QuoteLine("Running this service", service_cents),
    )
    total = sum(line.cents for line in lines)
    return Quote(
        currency=currency,
        lines=lines,
        total_cents=total,
        delivery_estimate=DELIVERY_ESTIMATE,
        disclaimer=DISCLAIMER,
    )


#: Characters that fit on the first printed page at the letter's type size,
#: measured from the rendered PDF rather than guessed. Used only to decide
#: one page versus two.
FIRST_PAGE_CHAR_BUDGET = 3050


def estimate_pages(plain_text: str) -> int:
    return 1 if len(plain_text) <= FIRST_PAGE_CHAR_BUDGET else 2
