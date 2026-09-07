"""The TypeScript and Python composers must produce identical letters.

`scripts/parity-expected.json` is generated from the TypeScript implementation
(`node scripts/gen-parity.mjs`), because that is the code the sender's browser
runs and therefore the code that produced the preview they approved. If this
test fails, the server would print something other than what was shown — which
is the one bug in this project that must never ship.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.letters.address import UsAddress
from app.letters.composer import (
    LetterInput,
    compose_letter,
    letter_fingerprint,
)
from app.letters.content import CONTENT_PATH

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED = json.loads((REPO_ROOT / "scripts" / "parity-expected.json").read_text("utf-8"))
INPUTS = {
    case["name"]: case
    for case in json.loads((REPO_ROOT / "scripts" / "parity-inputs.json").read_text("utf-8"))
}


def _compose(case: dict) -> object:
    a = case["address"]
    return compose_letter(
        LetterInput(
            address=UsAddress(
                line1=a["line1"], line2=a["line2"], city=a["city"], state=a["state"], zip=a["zip"]
            ),
            observations=case["observations"],
            note=case["note"],
            suggestions=case["suggestions"],
            date_iso=case["dateIso"],
        )
    )


def test_every_fixture_matches_the_typescript_output() -> None:
    assert EXPECTED, "no parity fixtures found"
    for expected in EXPECTED:
        case = INPUTS[expected["name"]]
        doc = _compose(case)
        assert doc.plain_text == expected["plainText"], (
            f"letter text differs for fixture {expected['name']!r}\n"
            f"--- python ---\n{doc.plain_text}\n--- typescript ---\n{expected['plainText']}"
        )
        assert letter_fingerprint(doc.plain_text) == expected["fingerprint"], expected["name"]
        assert list(doc.recipient_lines) == expected["recipientLines"], expected["name"]
        assert [b.kind for b in doc.blocks] == expected["blockKinds"], expected["name"]
        assert doc.content_version == expected["contentVersion"], expected["name"]


def test_shared_content_copies_are_identical() -> None:
    """A forgotten `sync-content` run must fail loudly, not ship two letters."""
    shared = (REPO_ROOT / "shared" / "letter_content.json").read_text("utf-8")
    backend_copy = CONTENT_PATH.read_text("utf-8")
    frontend_copy = (
        REPO_ROOT / "frontend" / "src" / "content" / "letter_content.json"
    ).read_text("utf-8")

    assert backend_copy == shared, "backend letter_content.json is stale — run scripts/sync-content.mjs"
    assert frontend_copy == shared, "frontend letter_content.json is stale — run scripts/sync-content.mjs"
