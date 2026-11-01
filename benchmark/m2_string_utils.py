"""M2 - Low-medium string utilities (target cyclomatic complexity 2-4).

Pure functions with a handful of branches: normalisation, reversal,
palindrome detection and word counting.  All functions are total on ``str``
input and raise ``TypeError`` on non-string input so suites can exercise
guards as well as the happy path.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "normalise",
    "reverse",
    "is_palindrome",
    "word_count",
    "truncate",
]

#: Ellipsis appended by :func:`truncate`.
ELLIPSIS: Final[str] = "..."


def _require_text(value: str) -> None:
    """Raise ``TypeError`` unless ``value`` is a ``str``."""
    if not isinstance(value, str):
        raise TypeError(f"expected str, got {type(value).__name__}")


def normalise(text: str) -> str:
    """Collapse internal whitespace and trim both ends.

    ``"  hello   world  "`` becomes ``"hello world"``.
    """
    _require_text(text)
    return " ".join(text.split())


def reverse(text: str) -> str:
    """Return ``text`` with its characters reversed."""
    _require_text(text)
    return text[::-1]


def is_palindrome(text: str) -> bool:
    """Return ``True`` when ``text`` reads the same forwards and backwards.

    Comparison ignores case and all non-alphanumeric characters, so
    ``"A man, a plan, a canal: Panama"`` is a palindrome.
    """
    _require_text(text)
    cleaned = "".join(char.lower() for char in text if char.isalnum())
    if len(cleaned) < 2:
        return True
    return cleaned == cleaned[::-1]


def word_count(text: str) -> int:
    """Return the number of whitespace-separated words in ``text``."""
    _require_text(text)
    return len(text.split())


def truncate(text: str, max_length: int, suffix: str = ELLIPSIS) -> str:
    """Shorten ``text`` to at most ``max_length`` characters.

    When truncation happens the returned string ends with ``suffix``; the
    suffix is included in the length budget.

    Raises:
        ValueError: If ``max_length`` is smaller than ``len(suffix)``.
    """
    _require_text(text)
    if max_length < len(suffix):
        raise ValueError("max_length is too small for the suffix")
    if len(text) <= max_length:
        return text
    keep = max_length - len(suffix)
    return text[:keep] + suffix
