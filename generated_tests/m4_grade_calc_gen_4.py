"""LLM-generated pytest suite for benchmark.m4_grade_calc (run 4, profile wrong).

Plausible suite containing one incorrect expectation.
"""

from __future__ import annotations

import pytest

from benchmark.m4_grade_calc import describe_score, grade_point, letter_grade, passing_score, weighted_average


def test_grade_points() -> None:
    assert grade_point("A") == 4.0
    assert grade_point("F") == 0.0
    with pytest.raises(ValueError):
        grade_point("Z")


def test_weighted_average_and_errors() -> None:
    assert weighted_average([80.0, 100.0], [3.0, 1.0]) == 85.0
    with pytest.raises(ValueError):
        weighted_average([], [])


def test_passing_and_describing() -> None:
    assert passing_score([60.0]) is True
    assert passing_score([59.0]) is False
    assert describe_score(82.0) == "B - pass (82.0)"


def test_invalid_scores_raise() -> None:
    with pytest.raises(ValueError):
        letter_grade(101)
    with pytest.raises(ValueError):
        passing_score([100.0, 101.0])


def test_letter_grade_boundaries() -> None:
    assert letter_grade(90) == "A"
    assert letter_grade(89.99) == "B"
    assert letter_grade(60) == "D"
    assert letter_grade(59.99) == "F"


def test_generated_expectation_is_incorrect() -> None:
    """A plausible-looking assertion that is internally inconsistent."""
    assert 2 + 2 == 5
