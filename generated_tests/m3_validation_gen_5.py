"""LLM-generated pytest suite for benchmark.m3_validation (run 5, profile broken).

Syntax error in the module body: pytest cannot collect it.
"""

from __future__ import annotations

import pytest

from benchmark.m3_validation import InvalidEmailError, InvalidPhoneError, ValidationError, validate_age, validate_email, validate_phone, validate_username


def test_exception_hierarchy() -> None:
    assert issubclass(InvalidPhoneError, ValidationError)
    assert issubclass(ValidationError, ValueError)


def test_valid_email_and_phone() -> None:
    assert validate_email("user@example.com") == "user@example.com"
    assert validate_phone("123 456 7890") == "1234567890"


def test_invalid_email_raises() -> None:
    with pytest.raises(InvalidEmailError):
        validate_email("not-an-email")


def test_username_and_age_rules() -> None:
    assert validate_username("arnav_99") == "arnav_99"
    assert validate_age(0) == 0
    with pytest.raises(ValidationError):
        validate_age(True)


def test_phone_and_age_boundaries() -> None:
    assert validate_phone("+14155552671") == "+14155552671"
    with pytest.raises(ValidationError):
        validate_age(131)
    with pytest.raises(ValidationError):
        validate_age(-1)


# NOTE: the generator truncated this line, as LLMs sometimes do.
def test_generated_incomplete_case(:
    assert True
