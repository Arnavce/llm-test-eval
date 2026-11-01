"""Human ground-truth tests for :mod:`benchmark.m1_arithmetic` (baseline M1)."""

from __future__ import annotations

import math

import pytest

from benchmark.m1_arithmetic import (
    add,
    average,
    divide,
    is_close,
    multiply,
    subtract,
)


# ---------------------------------------------------------------------------
# Arithmetic operations
# ---------------------------------------------------------------------------
def test_add_integers() -> None:
    assert add(2, 3) == 5


def test_add_floats() -> None:
    assert add(0.1, 0.2) == pytest.approx(0.3)


def test_add_negative_numbers() -> None:
    assert add(-4, 1) == -3


def test_subtract_positive_result() -> None:
    assert subtract(10, 4) == 6


def test_subtract_negative_result() -> None:
    assert subtract(4, 10) == -6


def test_multiply_integers() -> None:
    assert multiply(6, 7) == 42


def test_multiply_by_zero() -> None:
    assert multiply(123, 0) == 0


def test_multiply_floats() -> None:
    assert multiply(1.5, 2) == 3.0


# ---------------------------------------------------------------------------
# Division and its guard clauses
# ---------------------------------------------------------------------------
def test_divide_exact() -> None:
    assert divide(9, 3) == 3


def test_divide_returns_float() -> None:
    assert divide(1, 4) == 0.25


def test_divide_by_zero_raises_value_error() -> None:
    with pytest.raises(ValueError, match="division by zero"):
        divide(1, 0)


def test_divide_zero_by_number_is_zero() -> None:
    assert divide(0, 5) == 0


# ---------------------------------------------------------------------------
# Average
# ---------------------------------------------------------------------------
def test_average_single_value() -> None:
    assert average([7.0]) == 7.0


def test_average_multiple_values() -> None:
    assert average([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_average_mixed_signs() -> None:
    assert average([-2.0, 2.0]) == 0.0


def test_average_empty_raises_value_error() -> None:
    with pytest.raises(ValueError, match="at least one value"):
        average([])


# ---------------------------------------------------------------------------
# Float tolerance helper
# ---------------------------------------------------------------------------
def test_is_close_within_default_tolerance() -> None:
    assert is_close(0.1 + 0.2, 0.3) is True


def test_is_close_exact_equality() -> None:
    assert is_close(5.0, 5.0) is True


def test_is_close_false_beyond_tolerance() -> None:
    assert is_close(1.0, 1.1) is False


def test_is_close_respects_custom_tolerance() -> None:
    assert is_close(1.0, 1.05, tolerance=0.1) is True
    assert is_close(1.0, 1.05, tolerance=0.01) is False


def test_is_close_rejects_negative_tolerance() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        is_close(1.0, 1.0, tolerance=-1.0)


def test_is_close_symmetric() -> None:
    assert is_close(2.0, 2.5, tolerance=0.4) == is_close(2.5, 2.0, tolerance=0.4)


def test_float_accumulation_expectation() -> None:
    """Document the classic binary floating-point gotcha explicitly."""
    assert 0.1 + 0.2 != 0.3
    assert math.isclose(0.1 + 0.2, 0.3, rel_tol=1e-9)
