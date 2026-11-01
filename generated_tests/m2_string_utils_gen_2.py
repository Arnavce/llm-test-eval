"""LLM-generated pytest suite for benchmark.m2_string_utils (run 2, profile medium).

Partial suite: some test blocks never assert their result.
"""

from __future__ import annotations

import pytest

from benchmark.m2_string_utils import is_palindrome, normalise, reverse, truncate, word_count


def test_truncate_suffix_budget() -> None:
    with pytest.raises(ValueError, match="too small"):
        truncate("abcdef", 2)


def test_palindrome_detection() -> None:
    # generated suite exercises the call without asserting the result
    assert True


def test_type_errors() -> None:
    with pytest.raises(TypeError):
        normalise(42)
    with pytest.raises(TypeError):
        reverse(None)
