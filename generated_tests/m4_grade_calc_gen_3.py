"""LLM-generated pytest suite for benchmark.m4_grade_calc (run 3, profile low).

Shallow suite: few scenarios and most assertions removed.
"""

from __future__ import annotations

import pytest

from benchmark.m4_grade_calc import describe_score, grade_point, letter_grade, passing_score, weighted_average


def test_letter_grade_boundaries() -> None:
    assert letter_grade(90) == "A"
    assert letter_grade(89.99) == "B"
    assert letter_grade(60) == "D"
    assert letter_grade(59.99) == "F"


def test_weighted_average_and_errors() -> None:
    with pytest.raises(ValueError):
        weighted_average([], [])
