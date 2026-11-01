"""Human ground-truth tests for :mod:`benchmark.m3_validation` (baseline M3)."""

from __future__ import annotations

import pytest

from benchmark.m3_validation import (
    InvalidEmailError,
    InvalidPhoneError,
    ValidationError,
    validate_age,
    validate_email,
    validate_phone,
    validate_username,
)


# ---------------------------------------------------------------------------
# validate_email
# ---------------------------------------------------------------------------
def test_valid_email_is_returned() -> None:
    assert validate_email("Student.Name+tag@example.co.uk") == (
        "Student.Name+tag@example.co.uk"
    )


def test_valid_email_is_stripped() -> None:
    assert validate_email("  user@example.com  ") == "user@example.com"


@pytest.mark.parametrize(
    "bad_email",
    [
        "plainaddress",
        "@example.com",
        "user@",
        "user@example",
        "user@@example.com",
        "user name@example.com",
        "",
    ],
)
def test_invalid_emails_raise(bad_email: str) -> None:
    with pytest.raises(InvalidEmailError):
        validate_email(bad_email)


def test_email_longer_than_254_characters_raises() -> None:
    long_email = "a" * 250 + "@example.com"
    with pytest.raises(InvalidEmailError, match="254"):
        validate_email(long_email)


def test_email_non_string_raises() -> None:
    with pytest.raises(InvalidEmailError):
        validate_email(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_phone
# ---------------------------------------------------------------------------
def test_valid_phone_is_normalised() -> None:
    assert validate_phone("123 456 7890") == "1234567890"


def test_valid_phone_with_dashes() -> None:
    assert validate_phone("123-456-7890") == "1234567890"


def test_valid_phone_with_country_code() -> None:
    assert validate_phone("+14155552671") == "+14155552671"


@pytest.mark.parametrize(
    "bad_phone",
    ["12345", "1234567890123456", "abcdefghij", "123-456", ""],
)
def test_invalid_phones_raise(bad_phone: str) -> None:
    with pytest.raises(InvalidPhoneError):
        validate_phone(bad_phone)


def test_phone_non_string_raises() -> None:
    with pytest.raises(InvalidPhoneError):
        validate_phone(5551234567)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------
def test_valid_username() -> None:
    assert validate_username("arnav_99") == "arnav_99"


@pytest.mark.parametrize("bad_name", ["ab", "a" * 21, "bad name", "bad-name"])
def test_invalid_usernames_raise(bad_name: str) -> None:
    with pytest.raises(ValidationError):
        validate_username(bad_name)


def test_username_rejects_non_string() -> None:
    with pytest.raises(ValidationError):
        validate_username(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# validate_age
# ---------------------------------------------------------------------------
def test_valid_age_boundaries() -> None:
    assert validate_age(0) == 0
    assert validate_age(130) == 130


def test_age_below_zero_raises() -> None:
    with pytest.raises(ValidationError, match=">= 0"):
        validate_age(-1)


def test_age_above_maximum_raises() -> None:
    with pytest.raises(ValidationError, match="<= 130"):
        validate_age(131)


def test_age_rejects_bool() -> None:
    with pytest.raises(ValidationError):
        validate_age(True)  # type: ignore[arg-type]


def test_age_rejects_float_string() -> None:
    with pytest.raises(ValidationError):
        validate_age("30")  # type: ignore[arg-type]


def test_age_inconsistent_bounds_raise() -> None:
    with pytest.raises(ValidationError, match="minimum"):
        validate_age(10, minimum=20, maximum=10)


def test_age_custom_bounds() -> None:
    assert validate_age(21, minimum=18, maximum=65) == 21


def test_exception_hierarchy() -> None:
    assert issubclass(InvalidEmailError, ValidationError)
    assert issubclass(InvalidPhoneError, ValidationError)
    assert issubclass(ValidationError, ValueError)


# ---------------------------------------------------------------------------
# Additional contract details (finer-grained M3 validation rules)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad_email",
    [
        ".user@example.com",
        "user.@example.com",
        "user..name@example.com",
        "user@-example.com",
        "user@example-.com",
        "user@@example.com",
    ],
)
def test_email_structure_rules(bad_email: str) -> None:
    with pytest.raises(InvalidEmailError):
        validate_email(bad_email)


@pytest.mark.parametrize("bad_phone", ["12345abcde", "++14155552671", "1234567890+"])
def test_phone_character_rules(bad_phone: str) -> None:
    with pytest.raises(InvalidPhoneError):
        validate_phone(bad_phone)


def test_phone_strips_surrounding_whitespace() -> None:
    assert validate_phone(" 1234567890 ") == "1234567890"


@pytest.mark.parametrize(
    "bad_name",
    ["1user", "_user", "user__name", "a" * 21, "ab", "bad name", "bad-name"],
)
def test_username_structure_rules(bad_name: str) -> None:
    with pytest.raises(ValidationError):
        validate_username(bad_name)


def test_age_negative_minimum_is_rejected() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        validate_age(10, minimum=-1, maximum=100)
