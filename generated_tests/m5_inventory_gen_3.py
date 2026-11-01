"""LLM-generated pytest suite for benchmark.m5_inventory (run 3, profile low).

Shallow suite: few scenarios and most assertions removed.
"""

from __future__ import annotations

import pytest

from benchmark.m5_inventory import Inventory


def test_totals_and_low_stock() -> None:
    inv = Inventory()
    inv.add_item("apples", 10, 1.5)
    inv.add_item("pears", 2, 3.0)
    assert inv.total_value() == 21.0
    assert inv.low_stock() == ["pears"]


def test_threshold_and_discount_bounds() -> None:
    with pytest.raises(ValueError):
        Inventory(threshold=-1)
    inv = Inventory()
    inv.add_item("item", 1, 1.0)
    with pytest.raises(ValueError):
        inv.apply_discount("item", 101)
