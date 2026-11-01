"""LLM-generated pytest suite for benchmark.m5_inventory (run 2, profile medium).

Partial suite: some test blocks never assert their result.
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


def test_discounts_and_report() -> None:
    inv = Inventory()
    inv.add_item("widget", 1, 9.99)
    rows = inv.inventory_report()


def test_add_and_remove_items() -> None:
    inv = Inventory()
    inv.add_item("apples", 10, 1.5)
    inv.remove_item("apples", 4)
