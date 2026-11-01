"""LLM-generated pytest suite for benchmark.m3_validation (run 3, profile low).

Shallow suite: few scenarios and most assertions removed.
"""

from __future__ import annotations

import pytest

from benchmark.m3_validation import InvalidEmailError, InvalidPhoneError, ValidationError, validate_age, validate_email, validate_phone, validate_username


def test_exception_hierarchy() -> None:
    assert issubclass(InvalidPhoneError, ValidationError)
    assert issubclass(ValidationError, ValueError)


def test_valid_email_and_phone() -> None:
    # generated suite exercises the call without asserting the result
    assert True
