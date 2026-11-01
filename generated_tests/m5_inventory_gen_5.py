import pytest

from benchmark.m5_inventory import DEFAULT_THRESHOLD, Inventory


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

def test_default_threshold_value():
    assert DEFAULT_THRESHOLD == 5


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def test_init_default_threshold():
    inv = Inventory()
    assert inv._threshold == DEFAULT_THRESHOLD


def test_init_custom_threshold():
    inv = Inventory(threshold=10)
    assert inv._threshold == 10


def test_init_zero_threshold_allowed():
    inv = Inventory(threshold=0)
    assert inv._threshold == 0


def test_init_negative_threshold_raises():
    with pytest.raises(ValueError):
        Inventory(threshold=-1)


# ---------------------------------------------------------------------------
# add_item
# ---------------------------------------------------------------------------

def test_add_item_new():
    inv = Inventory()
    inv.add_item("apple", 3, 1.5)
    assert inv.stock_level("apple") == 3


def test_add_item_accumulates_quantity():
    inv = Inventory()
    inv.add_item("apple", 3, 1.5)
    inv.add_item("apple", 2, 1.5)
    assert inv.stock_level("apple") == 5


def test_add_item_keeps_old_price_when_new_higher():
    inv = Inventory()
    inv.add_item("apple", 1, 2.0)
    inv.add_item("apple", 1, 3.0)
    assert inv._items["apple"]["price"] == pytest.approx(2.0)


def test_add_item_lowers_price_when_new_lower():
    inv = Inventory()
    inv.add_item("apple", 1, 2.0)
    inv.add_item("apple", 1, 1.0)
    assert inv._items["apple"]["price"] == pytest.approx(1.0)


def test_add_item_zero_price_does_not_change_existing_price():
    inv = Inventory()
    inv.add_item("apple", 1, 2.0)
    inv.add_item("apple", 1, 0.0)
    assert inv._items["apple"]["price"] == pytest.approx(2.0)


def test_add_item_normalizes_name():
    inv = Inventory()
    inv.add_item("  Apple  ", 1, 1.0)
    assert inv.stock_level("apple") == 1
    assert inv.stock_level("APPLE") == 1


def test_add_item_zero_quantity_allowed():
    inv = Inventory()
    inv.add_item("apple", 0, 1.0)
    assert inv.stock_level("apple") == 0


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
        inv.add_item("apple", -1, 1.0)


def test_add_item_negative_price_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("apple", 1, -0.5)


# ---------------------------------------------------------------------------
# remove_item
# ---------------------------------------------------------------------------

def test_remove_item_basic():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    inv.remove_item("apple", 2)
    assert inv.stock_level("apple") == 3


def test_remove_item_all():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    inv.remove_item("apple", 5)
    assert inv.stock_level("apple") == 0


def test_remove_item_zero_quantity():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    inv.remove_item("apple", 0)
    assert inv.stock_level("apple") == 5


def test_remove_item_negative_quantity_raises():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("apple", -1)


def test_remove_item_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.remove_item("banana", 1)


def test_remove_item_too_many_raises():
    inv = Inventory()
    inv.add_item("apple", 2, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("apple", 3)


def test_remove_item_normalizes_name():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    inv.remove_item("  APPLE ", 2)
    assert inv.stock_level("apple") == 3


# ---------------------------------------------------------------------------
# restock
# ---------------------------------------------------------------------------

def test_restock_basic():
    inv = Inventory()
    inv.add_item("apple", 2, 1.0)
    result = inv.restock("apple", 3)
    assert result == 5
    assert inv.stock_level("apple") == 5


def test_restock_does_not_change_price():
    inv = Inventory()
    inv.add_item("apple", 2, 1.0)
    inv.restock("apple", 3)
    assert inv._items["apple"]["price"] == pytest.approx(1.0)


def test_restock_zero_raises():
    inv = Inventory()
    inv.add_item("apple", 2, 1.0)
    with pytest.raises(ValueError):
        inv.restock("apple", 0)


def test_restock_negative_raises():
    inv = Inventory()
    inv.add_item("apple", 2, 1.0)
    with pytest.raises(ValueError):
        inv.restock("apple", -1)


def test_restock_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.restock("banana", 1)


# ---------------------------------------------------------------------------
# stock_level
# ---------------------------------------------------------------------------

def test_stock_level_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.stock_level("banana")


def test_stock_level_normalizes_name():
    inv = Inventory()
    inv.add_item("apple", 4, 1.0)
    assert inv.stock_level("  Apple ") == 4


# ---------------------------------------------------------------------------
# total_value
# ---------------------------------------------------------------------------

def test_total_value_empty():
    inv = Inventory()
    assert inv.total_value() == pytest.approx(0.0)


def test_total_value_single():
    inv = Inventory()
    inv.add_item("apple", 3, 1.5)
    assert inv.total_value() == pytest.approx(4.5)


def test_total_value_multiple():
    inv = Inventory()
    inv.add_item("apple", 3, 1.5)
    inv.add_item("banana", 2, 2.0)
    assert inv.total_value() == pytest.approx(8.5)


def test_total_value_rounded():
    inv = Inventory()
    inv.add_item("apple", 3, 0.333)
    assert inv.total_value() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# low_stock
# ---------------------------------------------------------------------------

def test_low_stock_empty():
    inv = Inventory()
    assert inv.low_stock() == []


def test_low_stock_default_threshold():
    inv = Inventory()
    inv.add_item("apple", 5, 1.0)
    inv.add_item("banana", 6, 1.0)
    inv.add_item("cherry", 0, 1.0)
    assert inv.low_stock() == ["cherry", "apple"]


def test_low_stock_custom_threshold():
    inv = Inventory(threshold=2)
    inv.add_item("apple", 2, 1.0)
    inv.add_item("banana", 3, 1.0)
    assert inv.low_stock() == ["apple"]


def test_low_stock_zero_threshold():
    inv = Inventory(threshold=0)
    inv.add_item("apple", 0, 1.0)
    inv.add_item("banana", 1, 1.0)
    assert inv.low_stock() == ["apple"]


def test_low_stock_ordering_by_quantity_then_name():
    inv = Inventory(threshold=10)
    inv.add_item("b", 3, 1.0)
    inv.add_item("a", 3, 1.0)
    inv.add_item("c", 1, 1.0)
    assert inv.low_stock() == ["c", "a", "b"]


# ---------------------------------------------------------------------------
# apply_discount
# ---------------------------------------------------------------------------

def test_apply_discount_basic():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    new_price = inv.apply_discount("apple", 10)
    assert new_price == pytest.approx(9.0)
    assert inv._items["apple"]["price"] == pytest.approx(9.0)


def test_apply_discount_zero():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    assert inv.apply_discount("apple", 0) == pytest.approx(10.0)


def test_apply_discount_full():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    assert inv.apply_discount("apple", 100) == pytest.approx(0.0)


def test_apply_discount_capped_at_50():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    assert inv.apply_discount("apple", 80) == pytest.approx(5.0)


def test_apply_discount_rounds():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    assert inv.apply_discount("apple", 33) == pytest.approx(6.7)


def test_apply_discount_negative_raises():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("apple", -1)


def test_apply_discount_over_100_raises():
    inv = Inventory()
    inv.add_item("apple", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("apple", 101)


def test_apply_discount_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.apply_discount("banana", 10)


# ---------------------------------------------------------------------------
# bulk_restock
# ---------------------------------------------------------------------------

def test_bulk_restock_basic():
    inv = Inventory()
    inv.add_item("apple", 1, 1.0)
    inv.add_item("banana", 1, 1.0)
    missing = inv.bulk_restock({"apple": 2, "banana": 3})
    assert missing == []
    assert inv.stock_level("apple") == 3
    assert inv.stock_level("banana") == 4


def test_bulk_restock_unknown_reported():
    inv = Inventory()
    inv.add_item("apple", 1, 1.0)
    missing = inv.bulk_restock({"apple": 2, "banana": 3})
    assert missing == ["banana"]
    assert inv.stock_level("apple") == 3


def test_bulk_restock_non_positive_ignored():
    inv = Inventory()
    inv.add_item("apple", 1, 1.0)
    inv.bulk_restock({"apple": 0})
    assert inv.stock_level("apple") == 1
    inv.bulk_restock({"apple": -5})
    assert inv.stock_level("apple") == 1


def test_bulk_restock_empty_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.bulk_restock({})


def test_bulk_restock_normalizes_names():
    inv = Inventory()
    inv.add_item("apple", 1, 1.0)
    missing = inv.bulk_restock({"  APPLE ": 2})
    assert missing == []
    assert inv.stock_level("apple") == 3


# ---------------------------------------------------------------------------
# inventory_report
# ---------------------------------------------------------------------------

def test_inventory_report_empty():
    inv = Inventory()
    assert inv.inventory_report() == []


def test_inventory_report_single():
    inv = Inventory()
    inv.add_item("apple", 2, 1.5)
    report = inv.inventory_report()
    assert len(report) == 1
    row = report[0]
    assert row["name"] == "apple"
    assert row["quantity"] == pytest.approx(2.0)
    assert row["price"] == pytest.approx(1.5)
    assert row["value"] == pytest.approx(3.0)


def test_inventory_report_sorted_by_value_desc():
    inv = Inventory()
    inv.add_item("apple", 1, 1.0)
    inv.add_item("banana", 5, 2.0)
    inv.add_item("cherry", 2, 1.0)
    report = inv.inventory_report()
    names = [row["name"] for row in report]
    assert names == ["banana", "cherry", "apple"]


def test_inventory_report_tie_break_by_name():
    inv = Inventory()
    inv.add_item("b", 1, 1.0)
    inv.add_item("a", 1, 1.0)
    report = inv.inventory_report()
    names = [row["name"] for row in report]
    assert names == ["a", "b"]


def test_inventory_report_value_rounded():
    inv = Inventory()
    inv.add_item("apple", 3, 0.333)
    report = inv.inventory_report()
    assert report[0]["value"] == pytest.approx(1.0)
