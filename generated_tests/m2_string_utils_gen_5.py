"""LLM-generated pytest suite for benchmark.m2_string_utils (run 5, profile broken).

Syntax error in the module body: pytest cannot collect it.
"""

from __future__ import annotations

import pytest

from benchmark.m2_string_utils import is_palindrome, normalise, reverse, truncate, word_count


def test_type_errors() -> None:
    with pytest.raises(TypeError):
        normalise(42)
    with pytest.raises(TypeError):
        reverse(None)


def test_palindrome_detection() -> None:
    assert is_palindrome("A man, a plan, a canal: Panama") is True
    assert is_palindrome("hello") is False


def test_normalise_and_reverse() -> None:
    assert normalise("  hello   world  ") == "hello world"
    assert reverse("abc") == "cba"


def test_truncate_suffix_budget() -> None:
    with pytest.raises(ValueError, match="too small"):
        truncate("abcdef", 2)


def test_word_count_and_truncate() -> None:
    assert word_count("the quick brown fox") == 4
    assert truncate("abcdefghij", 8) == "abcde..."


# NOTE: the generator truncated this line, as LLMs sometimes do.
def test_generated_incomplete_case(:
    assert True
