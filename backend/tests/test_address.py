"""Address normalization, hashing and validation.

`NORMALIZATION_CASES` is the same fixture table the frontend runs in
`frontend/tests/address.test.ts`. The two implementations must agree, because
the hash derived from this key is what enforces the do-not-mail list: if they
disagree, a suppressed address gets a letter.
"""

from __future__ import annotations

from app.letters.address import (
    AddressError,
    UsAddress,
    address_hash,
    normalize_address_key,
    validate_us_address,
)

PEPPER = "test-pepper"

#: (address, expected key). Kept in sync with the TypeScript fixture table.
NORMALIZATION_CASES: list[tuple[UsAddress, str]] = [
    (
        UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843"),
        "414 W SAN ANTONIO ST||MARFA|TX|79843",
    ),
    (
        UsAddress("  414   w. san antonio st. ", "", " marfa ", "tx", "79843-1234"),
        "414 W SAN ANTONIO ST||MARFA|TX|79843",
    ),
    (
        UsAddress("9 Highland Ave", "Apt 4B", "Somerville", "MA", "02143"),
        "9 HIGHLAND AVE|APT 4B|SOMERVILLE|MA|02143",
    ),
    (
        UsAddress("9 Highland Ave", "apt. 4-b", "Somerville", "ma", "02143"),
        "9 HIGHLAND AVE|APT 4 B|SOMERVILLE|MA|02143",
    ),
    (
        UsAddress("1600 Amphitheatre Pkwy", "", "Mountain View", "CA", "94043-1351"),
        "1600 AMPHITHEATRE PKWY||MOUNTAIN VIEW|CA|94043",
    ),
]


def test_normalization_matches_the_shared_fixture_table() -> None:
    for address, expected in NORMALIZATION_CASES:
        assert normalize_address_key(address) == expected


def test_formatting_differences_do_not_change_the_key() -> None:
    a = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")
    b = UsAddress("414  w.  SAN antonio st.", "", "  Marfa", "tx", "79843-0001")
    assert normalize_address_key(a) == normalize_address_key(b)
    assert address_hash(a, PEPPER) == address_hash(b, PEPPER)


def test_different_addresses_hash_differently() -> None:
    a = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")
    b = UsAddress("415 W San Antonio St", "", "Marfa", "TX", "79843")
    c = UsAddress("414 W San Antonio St", "Apt 2", "Marfa", "TX", "79843")
    hashes = {address_hash(x, PEPPER) for x in (a, b, c)}
    assert len(hashes) == 3


def test_the_pepper_changes_the_hash() -> None:
    a = UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")
    assert address_hash(a, "one") != address_hash(a, "two")
    assert len(address_hash(a, PEPPER)) == 64


def test_printed_lines_omit_an_empty_second_line_and_uppercase_the_state() -> None:
    assert UsAddress("414 W San Antonio St", "", "Marfa", "tx", "79843").lines() == [
        "414 W San Antonio St",
        "Marfa, TX 79843",
    ]
    assert UsAddress("9 Highland Ave", "Apt 4B", "Somerville", "MA", "02143").lines() == [
        "9 Highland Ave",
        "Apt 4B",
        "Somerville, MA 02143",
    ]


def _expect_error(address: UsAddress, fragment: str) -> None:
    try:
        validate_us_address(address)
    except AddressError as exc:
        assert fragment.lower() in str(exc).lower(), f"{fragment!r} not in {exc!r}"
    else:  # pragma: no cover
        raise AssertionError(f"expected {address} to be rejected")


def test_validation_rejects_the_things_a_letter_cannot_be_sent_to() -> None:
    _expect_error(UsAddress("", "", "Marfa", "TX", "79843"), "street address is required")
    _expect_error(UsAddress("Main Street", "", "Marfa", "TX", "79843"), "starts with a number")
    _expect_error(UsAddress("PO Box 42", "", "Marfa", "TX", "79843"), "po box")
    _expect_error(UsAddress("P.O. BOX 42", "", "Marfa", "TX", "79843"), "po box")
    _expect_error(UsAddress("414 W San Antonio St", "", "", "TX", "79843"), "city is required")
    _expect_error(UsAddress("414 W San Antonio St", "", "Marfa", "XX", "79843"), "state")
    _expect_error(UsAddress("414 W San Antonio St", "", "Marfa", "TX", "7984"), "zip")
    _expect_error(UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843-12"), "zip")


def test_validation_accepts_and_tidies_a_good_address() -> None:
    cleaned = validate_us_address(
        UsAddress("  414  W San Antonio St ", " ", " Marfa ", "tx", " 79843 ")
    )
    assert cleaned == UsAddress("414 W San Antonio St", "", "Marfa", "TX", "79843")
    assert validate_us_address(
        UsAddress("9 Highland Ave", "Apt 4B", "Somerville", "MA", "02143-1234")
    ).zip == "02143-1234"
