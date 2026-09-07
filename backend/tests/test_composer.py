"""Letter composition: ordering, optionality, sanitization, determinism."""

from __future__ import annotations

import re

from app.letters.address import UsAddress
from app.letters.composer import (
    BulletList,
    LetterInput,
    Paragraph,
    compose_letter,
    format_letter_date,
    letter_fingerprint,
    sanitize_note,
    validate_selections,
)
from app.letters.content import load_content, note_max_chars

ADDRESS = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")


def _compose(**kwargs) -> object:
    return compose_letter(LetterInput(address=ADDRESS, date_iso="2026-09-07", **kwargs))


def test_selection_order_is_the_template_order_not_the_click_order() -> None:
    a = _compose(suggestions=["warmer_color", "shield", "turn_off"])
    b = _compose(suggestions=["turn_off", "shield", "warmer_color"])
    assert a.plain_text == b.plain_text

    content = load_content()
    bullets = [b for b in a.blocks if isinstance(b, BulletList)][-1].items
    assert bullets[0] == content["suggestions"]["turn_off"]["bullet"]
    assert bullets[-1] == content["suggestions"]["warmer_color"]["bullet"]


def test_no_observations_uses_the_neutral_sentence_not_an_empty_list() -> None:
    doc = _compose(observations=[])
    content = load_content()
    assert any(
        isinstance(b, Paragraph) and b.text == content["observations_none"] for b in doc.blocks
    )
    assert content["observations_lead"] not in doc.plain_text


def test_no_suggestions_omits_the_suggestions_block_entirely() -> None:
    doc = _compose(suggestions=[])
    content = load_content()
    assert content["suggestions_lead"] not in doc.plain_text
    assert content["suggestions_lead_single"] not in doc.plain_text
    # The letter still works: it explains and closes.
    assert content["paragraphs"]["explanation"] in doc.plain_text
    assert content["paragraphs"]["closing"] in doc.plain_text


def test_one_suggestion_uses_the_singular_lead() -> None:
    content = load_content()
    doc = _compose(suggestions=["shield"])
    assert content["suggestions_lead_single"] in doc.plain_text
    assert content["suggestions_lead"] not in doc.plain_text


def test_letter_never_contains_contact_details_or_a_from_block() -> None:
    """The sender is not identified and no one is given a way to reply to them.

    The footer does use the word "sender" — to say that the sender's identity is
    not being shared — so this checks for the shapes that would actually leak
    something: an email address, a phone number, or a return-address block.
    """
    doc = _compose(observations=["all_night"], suggestions=["shield"])
    text = doc.plain_text
    assert "@" not in text
    assert not re.search(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text)
    assert not re.search(r"(?im)^\s*from:", text)
    assert "Sincerely," not in text  # the sign-off is deliberately unsigned


def test_letter_avoids_enforcement_language() -> None:
    doc = _compose(
        observations=["all_night", "upward", "spill", "unused_area"],
        suggestions=["turn_off", "timer", "motion_sensor", "shield", "lower_brightness", "warmer_color"],
    )
    text = doc.plain_text.lower()
    banned = [
        "illegal", "unlawful", "violation", "ordinance", "code enforcement", "police",
        "lawsuit", "penalty", "citation", "fined", "prosecut", "must ", "required to",
    ]
    for word in banned:
        assert not re.search(rf"\b{re.escape(word.strip())}", text), (
            f"letter contains enforcement language: {word!r}"
        )


def test_note_is_sanitized_and_appears_as_its_own_bullet() -> None:
    doc = _compose(observations=["other"], note="It <b>shines</b>\tinto\nthe bedroom")
    content = load_content()
    bullets = [b for b in doc.blocks if isinstance(b, BulletList)][0].items
    assert bullets[-1] == f"{content['note_prefix']}It b shines /b into the bedroom"
    assert "<" not in doc.plain_text and ">" not in doc.plain_text


def test_note_is_truncated_to_the_published_limit() -> None:
    long_note = "a" * (note_max_chars() + 250)
    doc = _compose(observations=["other"], note=long_note)
    bullets = [b for b in doc.blocks if isinstance(b, BulletList)][0].items
    content = load_content()
    assert bullets[-1] == content["note_prefix"] + "a" * note_max_chars()


def test_empty_or_whitespace_note_adds_nothing() -> None:
    assert sanitize_note("   \n\t ") == ""
    doc = _compose(observations=["other"], note="   ")
    content = load_content()
    # 'other' alone with no usable note means no observation bullets at all.
    assert content["observations_none"] in doc.plain_text


def test_composition_is_deterministic() -> None:
    first = _compose(observations=["all_night", "spill"], suggestions=["timer", "shield"])
    second = _compose(observations=["all_night", "spill"], suggestions=["timer", "shield"])
    assert first.plain_text == second.plain_text
    assert letter_fingerprint(first.plain_text) == letter_fingerprint(second.plain_text)


def test_fingerprint_changes_when_anything_changes() -> None:
    base = _compose(observations=["all_night"], suggestions=["shield"])
    variants = [
        _compose(observations=["all_night"], suggestions=["timer"]),
        _compose(observations=["upward"], suggestions=["shield"]),
        _compose(observations=["all_night", "other"], note="one more thing", suggestions=["shield"]),
        compose_letter(
            LetterInput(
                address=UsAddress("415 W San Antonio St", "", "Marfa", "TX", "79843"),
                observations=["all_night"],
                suggestions=["shield"],
                date_iso="2026-09-07",
            )
        ),
    ]
    base_fp = letter_fingerprint(base.plain_text)
    for variant in variants:
        assert letter_fingerprint(variant.plain_text) != base_fp


def test_recipient_block_is_addressed_to_a_role_never_an_invented_name() -> None:
    doc = _compose()
    assert doc.recipient_lines[0] == load_content()["recipient_line"]
    assert "Dear " not in doc.plain_text
    assert doc.recipient_lines[1:] == tuple(ADDRESS.lines())


def test_dates_are_formatted_without_locale_dependence() -> None:
    assert format_letter_date("2026-09-07") == "September 7, 2026"
    assert format_letter_date("2026-01-01") == "January 1, 2026"
    assert format_letter_date("2026-12-31") == "December 31, 2026"
    assert format_letter_date("not-a-date") == "not-a-date"


def test_unknown_selection_keys_are_rejected_rather_than_ignored() -> None:
    validate_selections(["all_night"], ["shield"])
    try:
        validate_selections(["all_night", "nonsense"], [])
    except ValueError as exc:
        assert "nonsense" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a ValueError for an unknown observation")

    try:
        validate_selections([], ["floodlight_removal"])
    except ValueError as exc:
        assert "floodlight_removal" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a ValueError for an unknown suggestion")


def test_letter_mentions_the_service_and_the_opt_out() -> None:
    doc = _compose()
    assert "whyisthislighton.com" in doc.plain_text
    assert "no-more-letters" in doc.plain_text


def test_letter_acknowledges_that_lighting_has_a_purpose() -> None:
    doc = _compose(observations=["all_night", "upward", "spill", "unused_area"])
    text = doc.plain_text
    assert "safety" in text and "accessibility" in text
    assert "not a complaint" in text
