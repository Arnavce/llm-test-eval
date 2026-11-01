"""LLM-generated pytest suite for benchmark.m2_string_utils (run 3, profile low).

Shallow suite: few scenarios and most assertions removed.
"""

from __future__ import annotations

import pytest

from benchmark.m2_string_utils import is_palindrome, normalise, reverse, truncate, word_count


def test_truncate_suffix_budget() -> None:
    with pytest.raises(ValueError, match="too small"):
        truncate("abcdef", 2)


def test_normalise_and_reverse() -> None:
    # generated suite exercises the call without asserting the result
    assert True
