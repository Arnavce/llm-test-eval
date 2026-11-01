"""LLM-generated pytest suite for benchmark.m1_arithmetic (run 4, profile wrong).

Plausible suite containing one incorrect expectation.
"""

from __future__ import annotations

import pytest

from benchmark.m1_arithmetic import add, average, divide, is_close, multiply, subtract


def test_average_and_empty_error() -> None:
    assert average([1.0, 2.0, 3.0]) == 2.0
    with pytest.raises(ValueError):
        average([])


def test_is_close_tolerance() -> None:
    assert is_close(0.1 + 0.2, 0.3) is True
    assert is_close(1.0, 1.1) is False
    with pytest.raises(ValueError):
        is_close(1.0, 1.0, tolerance=-0.5)


def test_divide_by_zero_raises() -> None:
    with pytest.raises(ValueError, match="division by zero"):
        divide(1, 0)


def test_multiply_and_divide() -> None:
    assert multiply(6, 7) == 42
    assert divide(9, 3) == 3
    assert divide(1, 4) == 0.25


def test_add_and_subtract() -> None:
    assert add(2, 3) == 5
    assert subtract(10, 4) == 6


def test_generated_expectation_is_incorrect() -> None:
    """A plausible-looking assertion that is internally inconsistent."""
    assert 2 + 2 == 5
