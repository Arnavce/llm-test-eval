import pytest

from benchmark.m5_inventory import DEFAULT_THRESHOLD, Inventory


# ---------------------------------------------------------------------------
# Constants and construction
# ---------------------------------------------------------------------------

def test_default_threshold_value():
    assert DEFAULT_THRESHOLD == 5


def test_default_threshold_used():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    inv.add_item("b", 6, 1.0)
    assert inv.low_stock() == ["a"]


def test_constructor_custom_threshold():
    inv = Inventory(threshold=2)
    inv.add_item("a", 2, 1.0)
    inv.add_item("b", 3, 1.0)
    assert inv.low_stock() == ["a"]


def test_constructor_zero_threshold():
    inv = Inventory(threshold=0)
    inv.add_item("a", 0, 1.0)
    inv.add_item("b", 1, 1.0)
    assert inv.low_stock() == ["a"]


def test_constructor_negative_threshold_raises():
    with pytest.raises(ValueError):
        Inventory(threshold=-1)


# ---------------------------------------------------------------------------
# add_item
# ---------------------------------------------------------------------------

def test_add_item_new():
    inv = Inventory()
    inv.add_item("Widget", 3, 2.5)
    assert inv.stock_level("widget") == 3
    assert inv.total_value() == pytest.approx(7.5)


def test_add_item_accumulates_quantity():
    inv = Inventory()
    inv.add_item("a", 2, 1.0)
    inv.add_item("a", 3, 1.0)
    assert inv.stock_level("a") == 5


def test_add_item_keeps_old_price_when_new_higher():
    inv = Inventory()
    inv.add_item("a", 1, 2.0)
    inv.add_item("a", 1, 5.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(2.0)


def test_add_item_lowers_price_when_new_lower():
    inv = Inventory()
    inv.add_item("a", 1, 5.0)
    inv.add_item("a", 1, 2.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(2.0)


def test_add_item_zero_price_does_not_change_existing_price():
    inv = Inventory()
    inv.add_item("a", 1, 5.0)
    inv.add_item("a", 1, 0.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(5.0)


def test_add_item_zero_quantity_allowed():
    inv = Inventory()
    inv.add_item("a", 0, 1.0)
    assert inv.stock_level("a") == 0


def test_add_item_zero_price_allowed():
    inv = Inventory()
    inv.add_item("a", 1, 0.0)
    assert inv.total_value() == pytest.approx(0.0)


def test_add_item_name_normalized():
    inv = Inventory()
    inv.add_item("  Widget  ", 1, 1.0)
    assert inv.stock_level("WIDGET") == 1


def test_add_item_blank_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("   ", 1, 1.0)


def test_add_item_empty_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("", 1, 1.0)


def test_add_item_negative_quantity_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("a", -1, 1.0)


def test_add_item_negative_price_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("a", 1, -0.01)


# ---------------------------------------------------------------------------
# remove_item
# ---------------------------------------------------------------------------

def test_remove_item_reduces_stock():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    inv.remove_item("a", 2)
    assert inv.stock_level("a") == 3


def test_remove_item_all_stock():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    inv.remove_item("a", 5)
    assert inv.stock_level("a") == 0


def test_remove_item_zero_quantity():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    inv.remove_item("a", 0)
    assert inv.stock_level("a") == 5


def test_remove_item_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.remove_item("missing", 1)


def test_remove_item_negative_quantity_raises():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("a", -1)


def test_remove_item_too_much_raises():
    inv = Inventory()
    inv.add_item("a", 5, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("a", 6)


def test_remove_item_name_normalized():
    inv = Inventory()
    inv.add_item("Widget", 5, 1.0)
    inv.remove_item("  WIDGET ", 2)
    assert inv.stock_level("widget") == 3


# ---------------------------------------------------------------------------
# restock
# ---------------------------------------------------------------------------

def test_restock_returns_new_level():
    inv = Inventory()
    inv.add_item("a", 2, 1.0)
    assert inv.restock("a", 3) == 5
    assert inv.stock_level("a") == 5


def test_restock_does_not_change_price():
    inv = Inventory()
    inv.add_item("a", 1, 2.0)
    inv.restock("a", 10)
    assert inv.inventory_report()[0]["price"] == pytest.approx(2.0)


def test_restock_zero_raises():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    with pytest.raises(ValueError):
        inv.restock("a", 0)


def test_restock_negative_raises():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    with pytest.raises(ValueError):
        inv.restock("a", -5)


def test_restock_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.restock("missing", 1)


# ---------------------------------------------------------------------------
# stock_level
# ---------------------------------------------------------------------------

def test_stock_level_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.stock_level("missing")


def test_stock_level_returns_int():
    inv = Inventory()
    inv.add_item("a", 4, 1.0)
    level = inv.stock_level("a")
    assert isinstance(level, int)
    assert level == 4


# ---------------------------------------------------------------------------
# total_value
# ---------------------------------------------------------------------------

def test_total_value_empty():
    inv = Inventory()
    assert inv.total_value() == pytest.approx(0.0)


def test_total_value_multiple_items():
    inv = Inventory()
    inv.add_item("a", 2, 1.5)
    inv.add_item("b", 3, 2.0)
    assert inv.total_value() == pytest.approx(9.0)


def test_total_value_rounded():
    inv = Inventory()
    inv.add_item("a", 3, 0.333)
    assert inv.total_value() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# low_stock
# ---------------------------------------------------------------------------

def test_low_stock_empty():
    inv = Inventory()
    assert inv.low_stock() == []


def test_low_stock_threshold_inclusive():
    inv = Inventory(threshold=5)
    inv.add_item("a", 5, 1.0)
    inv.add_item("b", 6, 1.0)
    assert inv.low_stock() == ["a"]


def test_low_stock_ordering_zero_first_then_alpha():
    inv = Inventory(threshold=5)
    inv.add_item("zeta", 0, 1.0)
    inv.add_item("alpha", 0, 1.0)
    inv.add_item("beta", 3, 1.0)
    inv.add_item("gamma", 3, 1.0)
    assert inv.low_stock() == ["alpha", "zeta", "beta", "gamma"]


def test_low_stock_excludes_high_stock():
    inv = Inventory(threshold=2)
    inv.add_item("a", 10, 1.0)
    assert inv.low_stock() == []


# ---------------------------------------------------------------------------
# apply_discount
# ---------------------------------------------------------------------------

def test_apply_discount_basic():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    new_price = inv.apply_discount("a", 10)
    assert new_price == pytest.approx(9.0)
    assert inv.inventory_report()[0]["price"] == pytest.approx(9.0)


def test_apply_discount_zero_percent():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    assert inv.apply_discount("a", 0) == pytest.approx(10.0)


def test_apply_discount_hundred_percent():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    assert inv.apply_discount("a", 100) == pytest.approx(0.0)


def test_apply_discount_capped_at_fifty():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    assert inv.apply_discount("a", 80) == pytest.approx(5.0)


def test_apply_discount_exactly_fifty():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    assert inv.apply_discount("a", 50) == pytest.approx(5.0)


def test_apply_discount_rounds():
    inv = Inventory()
    inv.add_item("a", 1, 9.99)
    assert inv.apply_discount("a", 33) == pytest.approx(6.69)


def test_apply_discount_negative_percent_raises():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("a", -1)


def test_apply_discount_over_hundred_raises():
    inv = Inventory()
    inv.add_item("a", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("a", 101)


def test_apply_discount_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.apply_discount("missing", 10)


def test_apply_discount_name_normalized():
    inv = Inventory()
    inv.add_item("Widget", 1, 10.0)
    assert inv.apply_discount("  WIDGET ", 10) == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# bulk_restock
# ---------------------------------------------------------------------------

def test_bulk_restock_updates_known():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    inv.add_item("b", 1, 1.0)
    missing = inv.bulk_restock({"a": 5, "b": 2})
    assert missing == []
    assert inv.stock_level("a") == 6
    assert inv.stock_level("b") == 3


def test_bulk_restock_returns_missing_names():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    missing = inv.bulk_restock({"a": 2, "unknown": 3})
    assert missing == ["unknown"]
    assert inv.stock_level("a") == 3


def test_bulk_restock_ignores_non_positive():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    inv.bulk_restock({"a": 0, "a2": -5})
    assert inv.stock_level("a") == 1


def test_bulk_restock_empty_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.bulk_restock({})


def test_bulk_restock_name_normalized():
    inv = Inventory()
    inv.add_item("Widget", 1, 1.0)
    missing = inv.bulk_restock({"  WIDGET ": 4})
    assert missing == []
    assert inv.stock_level("widget") == 5


# ---------------------------------------------------------------------------
# inventory_report
# ---------------------------------------------------------------------------

def test_inventory_report_empty():
    inv = Inventory()
    assert inv.inventory_report() == []


def test_inventory_report_sorted_by_value_desc():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    inv.add_item("b", 10, 2.0)
    inv.add_item("c", 5, 1.0)
    rows = inv.inventory_report()
    assert [row["name"] for row in rows] == ["b", "c", "a"]


def test_inventory_report_tie_break_by_name():
    inv = Inventory()
    inv.add_item("zeta", 2, 1.0)
    inv.add_item("alpha", 2, 1.0)
    rows = inv.inventory_report()
    assert [row["name"] for row in rows] == ["alpha", "zeta"]


def test_inventory_report_row_keys_and_values():
    inv = Inventory()
    inv.add_item("a", 3, 2.5)
    rows = inv.inventory_report()
    assert len(rows) == 1
    row = rows[0]
    assert set(row.keys()) == {"name", "quantity", "price", "value"}
    assert row["name"] == "a"
    assert row["quantity"] == pytest.approx(3.0)
    assert row["price"] == pytest.approx(2.5)
    assert row["value"] == pytest.approx(7.5)


def test_inventory_report_value_rounded():
    inv = Inventory()
    inv.add_item("a", 3, 0.333)
    rows = inv.inventory_report()
    assert rows[0]["value"] == pytest.approx(1.0)
