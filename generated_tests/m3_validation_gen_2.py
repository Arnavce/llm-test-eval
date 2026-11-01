"""LLM-generated pytest suite for benchmark.m3_validation (run 2, profile medium).

Partial suite: some test blocks never assert their result.
"""

from __future__ import annotations

import pytest

from benchmark.m3_validation import InvalidEmailError, InvalidPhoneError, ValidationError, validate_age, validate_email, validate_phone, validate_username


def test_valid_email_and_phone() -> None:
    assert validate_email("user@example.com") == "user@example.com"
    assert validate_phone("123 456 7890") == "1234567890"


def test_username_and_age_rules() -> None:
    with pytest.raises(ValidationError):
        validate_age(True)


def test_phone_and_age_boundaries() -> None:
    with pytest.raises(ValidationError):
        validate_age(131)
    with pytest.raises(ValidationError):
        validate_age(-1)
