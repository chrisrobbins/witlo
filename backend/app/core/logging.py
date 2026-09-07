"""Logging, with a filter that keeps addresses and letter text out of the logs.

The privacy page promises that routine logs contain no recipient addresses or
letter content. A promise like that has to be enforced somewhere other than in
each developer's memory, so it is enforced here: a filter on the root logger
redacts anything that looks like a street address, a ZIP, or an email, and the
codebase logs letter *ids* rather than letter contents.

This is a backstop, not a licence to log sensitive values and rely on the regex.
"""

from __future__ import annotations

import logging
import re
import sys

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_ZIP = re.compile(r"\b\d{5}(-\d{4})?\b")
_STREET = re.compile(
    r"\b\d{1,6}\s+[\w.'-]+(\s+[\w.'-]+){0,4}\s+"
    r"(st|street|ave|avenue|rd|road|blvd|boulevard|ln|lane|dr|drive|ct|court|way|pkwy|parkway|hwy|highway|cir|circle|ter|terrace|pl|place)\b",
    re.IGNORECASE,
)


class RedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = _STREET.sub("[address]", message)
        redacted = _EMAIL.sub("[email]", redacted)
        redacted = _ZIP.sub("[zip]", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s :: %(message)s"))
    handler.addFilter(RedactionFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # These two are chatty and log full URLs, which can carry ids.
    logging.getLogger("httpx").setLevel("WARNING")
    logging.getLogger("httpcore").setLevel("WARNING")
