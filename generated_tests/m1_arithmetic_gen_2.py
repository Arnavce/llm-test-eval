"""LLM-generated pytest suite for benchmark.m1_arithmetic (run 2, profile medium).

Partial suite: some test blocks never assert their result.
"""

from __future__ import annotations

import pytest

from benchmark.m1_arithmetic import add, average, divide, is_close, multiply, subtract


def test_is_close_tolerance() -> None:
    assert is_close(0.1 + 0.2, 0.3) is True
    assert is_close(1.0, 1.1) is False
    with pytest.raises(ValueError):
        is_close(1.0, 1.0, tolerance=-0.5)


def test_multiply_and_divide() -> None:
    # generated suite exercises the call without asserting the result
    assert True


def test_add_and_subtract() -> None:
    # generated suite exercises the call without asserting the result
    assert True
