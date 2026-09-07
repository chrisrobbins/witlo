"""Loads the shared letter content.

`letter_content.json` in this package is a synced copy of
`/shared/letter_content.json`; the frontend carries an identical copy. Run
`node scripts/sync-content.mjs` after editing the shared file. `tests/test_parity.py`
fails if the copies drift.

Stdlib only, on purpose: this module and `composer.py` are the two places where
the exact words that get printed are decided, and they should be runnable and
testable without a web framework, a database or a network.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CONTENT_PATH = Path(__file__).with_name("letter_content.json")

OBSERVATION_KEYS = ("all_night", "upward", "spill", "unused_area", "other")
SUGGESTION_KEYS = (
    "turn_off",
    "timer",
    "motion_sensor",
    "shield",
    "lower_brightness",
    "warmer_color",
)


@lru_cache(maxsize=1)
def load_content() -> dict[str, Any]:
    """Parse and lightly validate the shared content file."""
    data = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))

    required = {
        "version",
        "recipient_line",
        "salutation",
        "paragraphs",
        "observations_lead",
        "observations_none",
        "observations",
        "note_prefix",
        "suggestions_lead",
        "suggestions_lead_single",
        "suggestions",
        "signoff_line",
        "signoff_name",
        "mascot_caption",
        "footer",
        "limits",
        "order",
    }
    missing = required - data.keys()
    if missing:
        raise ValueError(f"letter_content.json is missing keys: {sorted(missing)}")

    for key in ("opening", "acknowledgment", "explanation", "closing"):
        if key not in data["paragraphs"]:
            raise ValueError(f"letter_content.json is missing paragraph '{key}'")

    for key in OBSERVATION_KEYS:
        if key not in data["observations"]:
            raise ValueError(f"letter_content.json is missing observation '{key}'")

    for key in SUGGESTION_KEYS:
        if key not in data["suggestions"]:
            raise ValueError(f"letter_content.json is missing suggestion '{key}'")

    return data


def note_max_chars() -> int:
    return int(load_content()["limits"]["note_max_chars"])


def content_version() -> str:
    return str(load_content()["version"])
