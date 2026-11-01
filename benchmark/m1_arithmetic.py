"""M1 - Low-complexity arithmetic helpers (target cyclomatic complexity 1-3).

The module intentionally mixes a couple of defensive ``ValueError`` paths with
straight-line arithmetic so that even a weak generated suite can collect and
execute it, while boundary bugs in the guards are still detectable by a strong
suite.  No function contains a loop or a nested conditional.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "add",
    "subtract",
    "multiply",
    "divide",
    "average",
    "is_close",
]

#: Absolute tolerance used by :func:`is_close`.
DEFAULT_TOLERANCE: Final[float] = 1e-9


def add(a: float, b: float) -> float:
    """Return the sum of ``a`` and ``b``."""
    return a + b


def subtract(a: float, b: float) -> float:
    """Return ``a`` minus ``b``."""
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of ``a`` and ``b``."""
    return a * b


def divide(a: float, b: float) -> float:
    """Return ``a / b``.

    Raises:
        ValueError: If ``b`` is exactly zero (float or int zero).
    """
    if b == 0:
        raise ValueError("division by zero is not permitted")
    return a / b


def average(values: list[float]) -> float:
    """Return the arithmetic mean of ``values``.

    Raises:
        ValueError: If ``values`` is empty; a mean of nothing is undefined.
    """
    if not values:
        raise ValueError("average() requires at least one value")
    total = 0.0
    for value in values:
        total += value
    return total / len(values)


def is_close(a: float, b: float, tolerance: float = DEFAULT_TOLERANCE) -> bool:
    """Return ``True`` when ``abs(a - b) <= tolerance``.

    Raises:
        ValueError: If ``tolerance`` is negative.
    """
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")
    return abs(a - b) <= tolerance
