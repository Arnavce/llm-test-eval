"""Human ground-truth tests for :mod:`benchmark.m5_inventory` (baseline M5)."""

from __future__ import annotations

import pytest

from benchmark.m5_inventory import DEFAULT_THRESHOLD, Inventory


@pytest.fixture()
def inventory() -> Inventory:
    """A small seeded inventory: apples (10 @ 1.5), pears (2 @ 3.0)."""
    inv = Inventory()
    inv.add_item("Apples", 10, 1.5)
    inv.add_item("pears", 2, 3.0)
    return inv


# ---------------------------------------------------------------------------
# Construction and adding items
# ---------------------------------------------------------------------------
def test_new_inventory_is_empty() -> None:
    inv = Inventory()
    assert inv.total_value() == 0.0
    assert inv.inventory_report() == []
    assert inv.low_stock() == []


def test_add_new_item_stores_quantity_and_price(inventory: Inventory) -> None:
    assert inventory.stock_level("apples") == 10
    assert inventory.total_value() == pytest.approx(21.0)


def test_add_item_accumulates_quantity_and_keeps_lower_price() -> None:
    inv = Inventory()
    inv.add_item("milk", 2, 2.5)
    inv.add_item("MILK", 3, 9.99)
    assert inv.stock_level("milk") == 5
    assert inv.inventory_report()[0]["price"] == 2.5
    inv.add_item("milk", 1, 1.75)
    assert inv.inventory_report()[0]["price"] == 1.75


def test_add_item_trims_and_lowercases_name() -> None:
    inv = Inventory()
    inv.add_item("  Widget  ", 1, 1.0)
    assert inv.stock_level("widget") == 1


@pytest.mark.parametrize(
    ("name", "quantity", "price"),
    [
        ("", 1, 1.0),
        ("   ", 1, 1.0),
        ("ok", -1, 1.0),
        ("ok", 1, -0.5),
    ],
)
def test_add_item_validation(name: str, quantity: int, price: float) -> None:
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item(name, quantity, price)


def test_negative_threshold_is_rejected() -> None:
    with pytest.raises(ValueError, match="threshold"):
        Inventory(threshold=-1)


# ---------------------------------------------------------------------------
# Removing items
# ---------------------------------------------------------------------------
def test_remove_item_decrements_stock(inventory: Inventory) -> None:
    inventory.remove_item("apples", 4)
    assert inventory.stock_level("apples") == 6


def test_remove_item_to_zero(inventory: Inventory) -> None:
    inventory.remove_item("pears", 2)
    assert inventory.stock_level("pears") == 0


def test_remove_more_than_available_raises(inventory: Inventory) -> None:
    with pytest.raises(ValueError, match="more than available"):
        inventory.remove_item("apples", 11)


def test_remove_unknown_item_raises(inventory: Inventory) -> None:
    with pytest.raises(KeyError):
        inventory.remove_item("bananas", 1)


def test_remove_negative_quantity_raises(inventory: Inventory) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        inventory.remove_item("apples", -1)


def test_stock_level_unknown_item_raises() -> None:
    with pytest.raises(KeyError):
        Inventory().stock_level("ghost")


# ---------------------------------------------------------------------------
# Valuation, thresholds and discounts
# ---------------------------------------------------------------------------
def test_total_value_across_multiple_items() -> None:
    inv = Inventory()
    inv.add_item("a", 3, 2.0)
    inv.add_item("b", 2, 0.5)
    assert inv.total_value() == 7.0


def test_low_stock_uses_inclusive_threshold() -> None:
    inv = Inventory(threshold=5)
    inv.add_item("low", 5, 1.0)
    inv.add_item("high", 6, 1.0)
    assert inv.low_stock() == ["low"]


def test_low_stock_default_threshold_is_five() -> None:
    inv = Inventory()
    inv.add_item("edge", DEFAULT_THRESHOLD, 1.0)
    assert inv.low_stock() == ["edge"]


def test_low_stock_is_sorted(inventory: Inventory) -> None:
    assert inventory.low_stock() == ["pears"]


def test_apply_discount_reduces_price(inventory: Inventory) -> None:
    new_price = inventory.apply_discount("apples", 20)
    assert new_price == 1.2
    assert inventory.apply_discount("apples", 100) == 0.6


def test_apply_discount_rounds_to_cents() -> None:
    inv = Inventory()
    inv.add_item("round", 1, 9.99)
    assert inv.apply_discount("round", 15) == 8.49


@pytest.mark.parametrize("percent", [-1, 101, 150])
def test_apply_discount_rejects_out_of_range(inventory: Inventory, percent: float) -> None:
    with pytest.raises(ValueError, match="between 0 and 100"):
        inventory.apply_discount("apples", percent)


def test_apply_discount_unknown_item(inventory: Inventory) -> None:
    with pytest.raises(KeyError):
        inventory.apply_discount("ghost", 10)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def test_inventory_report_rows_and_ordering() -> None:
    inv = Inventory()
    inv.add_item("cheap", 10, 0.5)   # value 5.0
    inv.add_item("pricey", 1, 50.0)  # value 50.0
    rows = inv.inventory_report()
    assert [row["name"] for row in rows] == ["pricey", "cheap"]
    assert rows[0]["value"] == 50.0
    assert set(rows[0]) == {"name", "quantity", "price", "value"}


# ---------------------------------------------------------------------------
# Restocking, bulk orders and discount caps
# ---------------------------------------------------------------------------
def test_restock_increases_quantity_without_changing_price(inventory: Inventory) -> None:
    assert inventory.restock("apples", 5) == 15
    assert inventory.stock_level("apples") == 15
    assert inventory.inventory_report()[0]["price"] in {1.5, 3.0}


def test_restock_unknown_item_raises(inventory: Inventory) -> None:
    with pytest.raises(KeyError):
        inventory.restock("ghost", 1)


@pytest.mark.parametrize("quantity", [0, -3])
def test_restock_requires_positive_quantity(inventory: Inventory, quantity: int) -> None:
    with pytest.raises(ValueError, match="positive"):
        inventory.restock("apples", quantity)


def test_bulk_restock_updates_known_items_and_reports_unknown(inventory: Inventory) -> None:
    missing = inventory.bulk_restock({"apples": 5, "mystery": 2})
    assert missing == ["mystery"]
    assert inventory.stock_level("apples") == 15


def test_bulk_restock_ignores_non_positive_quantities(inventory: Inventory) -> None:
    inventory.bulk_restock({"apples": 0, "pears": -4})
    assert inventory.stock_level("apples") == 10
    assert inventory.stock_level("pears") == 2


def test_bulk_restock_empty_order_raises(inventory: Inventory) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        inventory.bulk_restock({})


def test_discount_is_capped_at_fifty_percent() -> None:
    inv = Inventory()
    inv.add_item("clearance", 1, 10.0)
    assert inv.apply_discount("clearance", 90) == 5.0
