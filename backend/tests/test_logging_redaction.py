"""The privacy page promises no addresses or letter content in routine logs.

This filter is the backstop that makes that promise enforceable rather than
aspirational. It is not a licence to log sensitive values.
"""

from __future__ import annotations

import logging

from app.core.logging import RedactionFilter


def _redact(message: str) -> str:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, message, (), None)
    RedactionFilter().filter(record)
    return record.getMessage()


def test_street_addresses_are_redacted() -> None:
    out = _redact("submitting letter to 414 W San Antonio St in Marfa")
    assert "414 W San Antonio St" not in out
    assert "[address]" in out


def test_a_variety_of_street_suffixes_are_caught() -> None:
    for line in (
        "9 Highland Ave",
        "1600 Amphitheatre Pkwy",
        "22 Oak Court",
        "5 Provider Down Lane",
        "300 Sunset Boulevard",
    ):
        assert "[address]" in _redact(f"mailing to {line} today"), line


def test_zip_codes_and_emails_are_redacted() -> None:
    out = _redact("recipient 79843 contacted sender@example.com")
    assert "79843" not in out
    assert "sender@example.com" not in out
    assert "[zip]" in out and "[email]" in out


def test_letter_ids_and_statuses_survive_so_logs_stay_useful() -> None:
    out = _redact("letter ltr_abc123 moved from paid to submitted")
    assert "ltr_abc123" in out
    assert "paid to submitted" in out


def test_the_filter_never_raises_on_odd_records() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "%s and %s", ("only-one",), None)
    assert RedactionFilter().filter(record) is True
