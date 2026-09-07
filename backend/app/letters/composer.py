"""Deterministic letter composition — the Python half of the pair.

This is a line-for-line mirror of `frontend/src/lib/letter.ts`. Given the same
inputs both produce the same `plain_text` and the same fingerprint;
`tests/test_parity.py` proves it against a shared fixture table so the letter a
sender approved in their browser is provably the letter that gets printed.

No LLM, no randomness, no clock except the date passed in.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal, Sequence

from .address import UsAddress
from .content import OBSERVATION_KEYS, SUGGESTION_KEYS, load_content, note_max_chars

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)

_CONTROL = re.compile(r"[\u0000-\u001F\u007F-\u009F]")
_MARKUP = re.compile(r"[<>{}\\]")
_WHITESPACE = re.compile(r"\s+")
_BLANK_RUN = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class Paragraph:
    text: str
    kind: Literal["paragraph"] = "paragraph"


@dataclass(frozen=True, slots=True)
class BulletList:
    lead: str
    items: tuple[str, ...]
    kind: Literal["list"] = "list"


Block = Paragraph | BulletList


@dataclass(frozen=True, slots=True)
class LetterInput:
    address: UsAddress
    observations: Sequence[str] = ()
    note: str = ""
    suggestions: Sequence[str] = ()
    date_iso: str = ""


@dataclass(frozen=True, slots=True)
class LetterDocument:
    content_version: str
    date: str
    recipient_lines: tuple[str, ...]
    salutation: str
    blocks: tuple[Block, ...]
    signoff_line: str
    signoff_name: str
    mascot_caption: str
    footer: str
    plain_text: str = field(default="")


def format_letter_date(date_iso: str) -> str:
    """'2026-09-07' -> 'September 7, 2026'. Locale-independent on purpose."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date_iso.strip())
    if not m:
        return date_iso
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    name = MONTHS[month - 1] if 1 <= month <= 12 else m.group(2)
    return f"{name} {day}, {year}"


def today_iso(today: date | None = None) -> str:
    return (today or date.today()).isoformat()


def sanitize_note(raw: str) -> str:
    """Strip control characters and anything markup-shaped, collapse whitespace.

    Removed rather than escaped: this string is printed onto paper as well as
    rendered in HTML, and `&lt;` on a page of paper looks like a mistake.
    """
    collapsed = _WHITESPACE.sub(" ", _MARKUP.sub(" ", _CONTROL.sub(" ", raw))).strip()
    if not collapsed:
        return ""
    return collapsed[: note_max_chars()]


def _ordered(selected: Sequence[str], order: Sequence[str]) -> list[str]:
    chosen = set(selected)
    return [key for key in order if key in chosen]


def compose_letter(data: LetterInput) -> LetterDocument:
    content = load_content()

    observation_order = content["order"]["observations"]
    suggestion_order = content["order"]["suggestions"]

    observations = _ordered(data.observations, observation_order)
    suggestions = _ordered(data.suggestions, suggestion_order)
    note = sanitize_note(data.note)

    observation_items: list[str] = [content["observations"][k]["bullet"] for k in observations]
    if note:
        observation_items.append(f"{content['note_prefix']}{note}")

    blocks: list[Block] = [Paragraph(content["paragraphs"]["opening"])]

    if observation_items:
        blocks.append(BulletList(content["observations_lead"], tuple(observation_items)))
    else:
        blocks.append(Paragraph(content["observations_none"]))

    blocks.append(Paragraph(content["paragraphs"]["acknowledgment"]))
    blocks.append(Paragraph(content["paragraphs"]["explanation"]))

    if suggestions:
        lead = (
            content["suggestions_lead_single"]
            if len(suggestions) == 1
            else content["suggestions_lead"]
        )
        blocks.append(
            BulletList(lead, tuple(content["suggestions"][k]["bullet"] for k in suggestions))
        )

    blocks.append(Paragraph(content["paragraphs"]["closing"]))

    doc = LetterDocument(
        content_version=content["version"],
        date=format_letter_date(data.date_iso or today_iso()),
        recipient_lines=(content["recipient_line"], *data.address.lines()),
        salutation=content["salutation"],
        blocks=tuple(blocks),
        signoff_line=content["signoff_line"],
        signoff_name=content["signoff_name"],
        mascot_caption=content["mascot_caption"],
        footer=content["footer"],
    )
    return replace(doc, plain_text=render_plain_text(doc))


def render_plain_text(doc: LetterDocument) -> str:
    """The canonical text form, hashed for preview/send integrity checks."""
    parts: list[str] = [doc.date, "", "\n".join(doc.recipient_lines), "", doc.salutation, ""]
    for block in doc.blocks:
        if isinstance(block, Paragraph):
            parts.append(block.text)
        else:
            parts.append(block.lead)
            parts.extend(f"  - {item}" for item in block.items)
        parts.append("")
    parts.extend(
        [doc.signoff_line, doc.signoff_name, "", doc.mascot_caption, "", "---", doc.footer]
    )
    return _BLANK_RUN.sub("\n\n", "\n".join(parts)).strip() + "\n"


def letter_fingerprint(plain_text: str) -> str:
    """FNV-1a 32-bit over UTF-8 bytes, 8 hex chars.

    Not a security primitive — a cheap change-detector shared with the browser
    so a submission can be checked against the preview the sender saw. The
    server always recomposes the letter itself; the fingerprint only decides
    whether to reject a mismatch.
    """
    h = 0x811C9DC5
    for byte in plain_text.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def validate_selections(observations: Sequence[str], suggestions: Sequence[str]) -> None:
    """Reject unknown keys rather than silently dropping them."""
    bad_obs = sorted(set(observations) - set(OBSERVATION_KEYS))
    if bad_obs:
        raise ValueError(f"Unknown observation(s): {bad_obs}")
    bad_sug = sorted(set(suggestions) - set(SUGGESTION_KEYS))
    if bad_sug:
        raise ValueError(f"Unknown suggestion(s): {bad_sug}")
