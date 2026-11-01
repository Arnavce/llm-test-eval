"""Human ground-truth tests for :mod:`benchmark.m2_string_utils` (baseline M2)."""

from __future__ import annotations

import pytest

from benchmark.m2_string_utils import (
    is_palindrome,
    normalise,
    reverse,
    truncate,
    word_count,
)


# ---------------------------------------------------------------------------
# normalise
# ---------------------------------------------------------------------------
def test_normalise_collapses_internal_whitespace() -> None:
    assert normalise("  hello   world  ") == "hello world"


def test_normalise_handles_tabs_and_newlines() -> None:
    assert normalise("a\tb\nc") == "a b c"


def test_normalise_blank_string() -> None:
    assert normalise("   ") == ""


def test_normalise_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        normalise(42)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# reverse
# ---------------------------------------------------------------------------
def test_reverse_basic() -> None:
    assert reverse("abc") == "cba"


def test_reverse_empty_string() -> None:
    assert reverse("") == ""


def test_reverse_palindrome_is_unchanged() -> None:
    assert reverse("level") == "level"


def test_reverse_rejects_non_string() -> None:
    with pytest.raises(TypeError):
        reverse(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# is_palindrome
# ---------------------------------------------------------------------------
def test_palindrome_simple_word() -> None:
    assert is_palindrome("racecar") is True


def test_palindrome_ignores_case_and_punctuation() -> None:
    assert is_palindrome("A man, a plan, a canal: Panama") is True


def test_is_palindrome_false_case() -> None:
    assert is_palindrome("hello") is False


def test_is_palindrome_empty_and_single_character() -> None:
    assert is_palindrome("") is True
    assert is_palindrome("x") is True


def test_is_palindrome_only_punctuation() -> None:
    assert is_palindrome("!!!") is True


# ---------------------------------------------------------------------------
# word_count
# ---------------------------------------------------------------------------
def test_word_count_simple_sentence() -> None:
    assert word_count("the quick brown fox") == 4


def test_word_count_extra_whitespace() -> None:
    assert word_count("   spaced    out   ") == 2


def test_word_count_empty_string() -> None:
    assert word_count("") == 0


# ---------------------------------------------------------------------------
# truncate
# ---------------------------------------------------------------------------
def test_truncate_shorter_than_limit_is_unchanged() -> None:
    assert truncate("hi", 5) == "hi"


def test_truncate_exact_length_is_unchanged() -> None:
    assert truncate("hello", 5) == "hello"


def test_truncate_longer_string_appends_suffix() -> None:
    result = truncate("abcdefghij", 8)
    assert result == "abcde" + "..."
    assert len(result) == 8


def test_truncate_custom_suffix() -> None:
    assert truncate("abcdefghij", 6, suffix="~") == "abcde~"


def test_truncate_rejects_limit_smaller_than_suffix() -> None:
    with pytest.raises(ValueError, match="too small"):
        truncate("abcdef", 2)


def test_truncate_rejects_non_string_input() -> None:
    with pytest.raises(TypeError):
        truncate(123, 5)  # type: ignore[arg-type]
