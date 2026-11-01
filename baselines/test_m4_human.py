"""Human ground-truth tests for :mod:`benchmark.m4_grade_calc` (baseline M4)."""

from __future__ import annotations

import pytest

from benchmark.m4_grade_calc import (
    GRADE_POINTS,
    describe_score,
    grade_point,
    letter_grade,
    passing_score,
    weighted_average,
)


# ---------------------------------------------------------------------------
# letter_grade boundaries
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "A"),
        (90, "A"),
        (89.99, "B"),
        (80, "B"),
        (79.5, "C"),
        (70, "C"),
        (69.99, "D"),
        (60, "D"),
        (59.99, "F"),
        (0, "F"),
    ],
)
def test_letter_grade_boundaries(score: float, expected: str) -> None:
    assert letter_grade(score) == expected


@pytest.mark.parametrize("bad_score", [-0.1, 100.1, 101, -50])
def test_letter_grade_out_of_range_raises(bad_score: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        letter_grade(bad_score)


@pytest.mark.parametrize("bad_score", ["90", None, True])
def test_letter_grade_rejects_non_numeric(bad_score: object) -> None:
    with pytest.raises(ValueError):
        letter_grade(bad_score)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# grade_point
# ---------------------------------------------------------------------------
def test_grade_point_mapping() -> None:
    assert grade_point("A") == 4.0
    assert grade_point("B") == 3.0
    assert grade_point("C") == 2.0
    assert grade_point("D") == 1.0
    assert grade_point("F") == 0.0


def test_grade_point_is_case_and_whitespace_insensitive() -> None:
    assert grade_point(" a ") == 4.0


def test_grade_point_unknown_letter_raises() -> None:
    with pytest.raises(ValueError, match="unknown letter grade"):
        grade_point("Z")


def test_grade_point_non_string_raises() -> None:
    with pytest.raises(ValueError):
        grade_point(4)  # type: ignore[arg-type]


def test_grade_points_table_is_complete() -> None:
    assert set(GRADE_POINTS) == {"A", "B", "C", "D", "F"}


# ---------------------------------------------------------------------------
# weighted_average
# ---------------------------------------------------------------------------
def test_weighted_average_equal_weights() -> None:
    assert weighted_average([80.0, 90.0], [1.0, 1.0]) == 85.0


def test_weighted_average_unequal_weights() -> None:
    assert weighted_average([80.0, 100.0], [3.0, 1.0]) == 85.0


def test_weighted_average_single_value() -> None:
    assert weighted_average([77.77], [1.0]) == 77.77


def test_weighted_average_rounds_to_two_decimals() -> None:
    assert weighted_average([1.0, 2.0, 2.0], [1.0, 2.0, 2.0]) == 1.8


def test_weighted_average_empty_raises() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        weighted_average([], [])


def test_weighted_average_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="same length"):
        weighted_average([80.0], [1.0, 2.0])


def test_weighted_average_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        weighted_average([80.0], [0.0])


def test_weighted_average_negative_weight_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        weighted_average([80.0, 90.0], [1.0, -1.0])


# ---------------------------------------------------------------------------
# passing_score
# ---------------------------------------------------------------------------
def test_passing_score_true_at_boundary() -> None:
    assert passing_score([60.0]) is True


def test_passing_score_uses_mean() -> None:
    assert passing_score([50.0, 70.0]) is True


def test_passing_score_false_below_boundary() -> None:
    assert passing_score([59.0, 59.0]) is False


def test_passing_score_empty_list_is_false() -> None:
    assert passing_score([]) is False


def test_passing_score_invalid_score_raises() -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        passing_score([100.0, 101.0])


# ---------------------------------------------------------------------------
# describe_score
# ---------------------------------------------------------------------------
def test_describe_score_pass() -> None:
    assert describe_score(82.0) == "B - pass (82.0)"


def test_describe_score_fail() -> None:
    assert describe_score(45.5) == "F - fail (45.5)"


def test_describe_score_out_of_range_raises() -> None:
    with pytest.raises(ValueError):
        describe_score(150)
