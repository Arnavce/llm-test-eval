"""LLM-generated pytest suite for benchmark.m5_inventory (run 1, profile high).

Complete suite: every behaviour and guard is asserted.
"""

from __future__ import annotations

import pytest

from benchmark.m5_inventory import Inventory


def test_invalid_operations_raise() -> None:
    inv = Inventory()
    inv.add_item("apples", 1, 1.0)
    with pytest.raises(KeyError):
        inv.remove_item("ghost", 1)
    with pytest.raises(ValueError):
        inv.add_item("", 1, 1.0)


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


def test_add_and_remove_items() -> None:
    inv = Inventory()
    inv.add_item("apples", 10, 1.5)
    inv.remove_item("apples", 4)
    assert inv.stock_level("apples") == 6


def test_discounts_and_report() -> None:
    inv = Inventory()
    inv.add_item("widget", 1, 9.99)
    assert inv.apply_discount("widget", 15) == 8.49
    rows = inv.inventory_report()
    assert rows[0]["name"] == "widget"
