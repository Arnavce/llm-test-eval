"""M4 - Medium-complexity grade calculation (target complexity 4-6).

Converts numeric scores into letter grades, letter grades into GPA points and
computes weighted aggregates.  The boundary behaviour at 60/70/80/90 is the
interesting part of the contract and is what strong test suites pin down.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "GRADE_POINTS",
    "letter_grade",
    "grade_point",
    "weighted_average",
    "passing_score",
    "describe_score",
]

#: Mapping from letter grade to the standard 4.0-scale grade point.
GRADE_POINTS: Final[dict[str, float]] = {
    "A": 4.0,
    "B": 3.0,
    "C": 2.0,
    "D": 1.0,
    "F": 0.0,
}

#: Lowest score that still passes the course.
PASSING_SCORE: Final[int] = 60


def letter_grade(score: float) -> str:
    """Map a 0-100 ``score`` to a letter grade.

    Boundaries are inclusive at the top of each band: ``90`` is an ``A``,
    ``89.99`` is a ``B``.

    Raises:
        ValueError: If ``score`` is not a number or is outside ``[0, 100]``.
    """
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("score must be numeric")
    if score < 0 or score > 100:
        raise ValueError("score must be between 0 and 100")
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def grade_point(letter: str) -> float:
    """Return the GPA points for ``letter``.

    Raises:
        ValueError: If ``letter`` is not one of ``A``, ``B``, ``C``, ``D``, ``F``.
    """
    if not isinstance(letter, str):
        raise ValueError("letter grade must be a string")
    key = letter.strip().upper()
    if key not in GRADE_POINTS:
        raise ValueError(f"unknown letter grade: {letter!r}")
    return GRADE_POINTS[key]


def weighted_average(scores: list[float], weights: list[float]) -> float:
    """Return the weighted mean of ``scores``, rounded to 2 decimals.

    Raises:
        ValueError: If the lists are empty, of different lengths, or all
            weights are zero.
    """
    if not scores:
        raise ValueError("scores must not be empty")
    if len(scores) != len(weights):
        raise ValueError("scores and weights must have the same length")
    total_weight = 0.0
    weighted_total = 0.0
    for score, weight in zip(scores, weights):
        if weight < 0:
            raise ValueError("weights must be non-negative")
        weighted_total += score * weight
        total_weight += weight
    if total_weight == 0:
        raise ValueError("at least one weight must be positive")
    return round(weighted_total / total_weight, 2)


def passing_score(scores: list[float]) -> bool:
    """Return ``True`` when the mean of ``scores`` is at least 60.

    An empty list is a failing result rather than an error: no submitted work
    means no credit.

    Raises:
        ValueError: If any score is outside ``[0, 100]``.
    """
    if not scores:
        return False
    for score in scores:
        if score < 0 or score > 100:
            raise ValueError("scores must be between 0 and 100")
    return sum(scores) / len(scores) >= PASSING_SCORE


def describe_score(score: float) -> str:
    """Return a short human-readable description of ``score``.

    Combines the letter grade with a pass/fail remark, e.g.
    ``"B - pass (82.0)"``.

    Raises:
        ValueError: If ``score`` is outside ``[0, 100]``.
    """
    letter = letter_grade(score)
    if letter == "F":
        status = "fail"
    else:
        status = "pass"
    return f"{letter} - {status} ({float(score):.1f})"
