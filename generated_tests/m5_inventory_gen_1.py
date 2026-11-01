import pytest

from benchmark.m5_inventory import DEFAULT_THRESHOLD, Inventory


# ---------------------------------------------------------------------------
# Constants and construction
# ---------------------------------------------------------------------------

def test_default_threshold_value():
    assert DEFAULT_THRESHOLD == 5


def test_default_construction_uses_default_threshold():
    inv = Inventory()
    inv.add_item("widget", 5, 1.0)
    # quantity == threshold (5) counts as low stock
    assert inv.low_stock() == ["widget"]


def test_construction_with_zero_threshold():
    inv = Inventory(threshold=0)
    inv.add_item("a", 0, 1.0)
    inv.add_item("b", 1, 1.0)
    assert inv.low_stock() == ["a"]


def test_construction_negative_threshold_raises():
    with pytest.raises(ValueError):
        Inventory(threshold=-1)


# ---------------------------------------------------------------------------
# add_item
# ---------------------------------------------------------------------------

def test_add_item_new_item():
    inv = Inventory()
    inv.add_item("Widget", 3, 2.5)
    assert inv.stock_level("widget") == 3
    assert inv.total_value() == pytest.approx(7.5)


def test_add_item_accumulates_quantity():
    inv = Inventory()
    inv.add_item("widget", 3, 2.0)
    inv.add_item("widget", 4, 2.0)
    assert inv.stock_level("widget") == 7


def test_add_item_keeps_old_price_when_new_price_higher():
    inv = Inventory()
    inv.add_item("widget", 1, 2.0)
    inv.add_item("widget", 1, 5.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(2.0)


def test_add_item_lowers_price_when_new_price_lower():
    inv = Inventory()
    inv.add_item("widget", 1, 5.0)
    inv.add_item("widget", 1, 2.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(2.0)


def test_add_item_zero_price_does_not_lower_existing_price():
    inv = Inventory()
    inv.add_item("widget", 1, 5.0)
    inv.add_item("widget", 1, 0.0)
    report = inv.inventory_report()
    assert report[0]["price"] == pytest.approx(5.0)


def test_add_item_zero_quantity_allowed():
    inv = Inventory()
    inv.add_item("widget", 0, 1.0)
    assert inv.stock_level("widget") == 0


def test_add_item_zero_price_allowed():
    inv = Inventory()
    inv.add_item("widget", 2, 0.0)
    assert inv.total_value() == pytest.approx(0.0)


def test_add_item_name_is_normalized():
    inv = Inventory()
    inv.add_item("  Widget  ", 1, 1.0)
    assert inv.stock_level("WIDGET") == 1


def test_add_item_negative_quantity_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("widget", -1, 1.0)


def test_add_item_negative_price_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("widget", 1, -0.01)


def test_add_item_blank_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("   ", 1, 1.0)


def test_add_item_empty_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("", 1, 1.0)


def test_add_item_non_string_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item(None, 1, 1.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# remove_item
# ---------------------------------------------------------------------------

def test_remove_item_reduces_stock():
    inv = Inventory()
    inv.add_item("widget", 5, 1.0)
    inv.remove_item("widget", 2)
    assert inv.stock_level("widget") == 3


def test_remove_item_all_stock():
    inv = Inventory()
    inv.add_item("widget", 5, 1.0)
    inv.remove_item("widget", 5)
    assert inv.stock_level("widget") == 0


def test_remove_item_zero_quantity_is_noop():
    inv = Inventory()
    inv.add_item("widget", 5, 1.0)
    inv.remove_item("widget", 0)
    assert inv.stock_level("widget") == 5


def test_remove_item_negative_quantity_raises():
    inv = Inventory()
    inv.add_item("widget", 5, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("widget", -1)


def test_remove_item_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.remove_item("missing", 1)


def test_remove_item_more_than_available_raises():
    inv = Inventory()
    inv.add_item("widget", 2, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("widget", 3)


def test_remove_item_name_normalized():
    inv = Inventory()
    inv.add_item("Widget", 5, 1.0)
    inv.remove_item("  WIDGET ", 1)
    assert inv.stock_level("widget") == 4


# ---------------------------------------------------------------------------
# restock
# ---------------------------------------------------------------------------

def test_restock_increases_and_returns_level():
    inv = Inventory()
    inv.add_item("widget", 2, 1.0)
    result = inv.restock("widget", 3)
    assert result == 5
    assert inv.stock_level("widget") == 5


def test_restock_does_not_change_price():
    inv = Inventory()
    inv.add_item("widget", 2, 4.0)
    inv.restock("widget", 3)
    assert inv.inventory_report()[0]["price"] == pytest.approx(4.0)


def test_restock_zero_raises():
    inv = Inventory()
    inv.add_item("widget", 2, 1.0)
    with pytest.raises(ValueError):
        inv.restock("widget", 0)


def test_restock_negative_raises():
    inv = Inventory()
    inv.add_item("widget", 2, 1.0)
    with pytest.raises(ValueError):
        inv.restock("widget", -5)


def test_restock_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.restock("missing", 1)


# ---------------------------------------------------------------------------
# stock_level
# ---------------------------------------------------------------------------

def test_stock_level_returns_int():
    inv = Inventory()
    inv.add_item("widget", 3, 1.0)
    level = inv.stock_level("widget")
    assert isinstance(level, int)
    assert level == 3


def test_stock_level_unknown_raises_keyerror():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.stock_level("missing")


# ---------------------------------------------------------------------------
# total_value
# ---------------------------------------------------------------------------

def test_total_value_empty_is_zero():
    inv = Inventory()
    assert inv.total_value() == pytest.approx(0.0)


def test_total_value_sums_items():
    inv = Inventory()
    inv.add_item("a", 2, 1.5)
    inv.add_item("b", 3, 2.0)
    assert inv.total_value() == pytest.approx(9.0)


def test_total_value_rounds_to_two_decimals():
    inv = Inventory()
    inv.add_item("a", 3, 0.333)
    assert inv.total_value() == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# low_stock
# ---------------------------------------------------------------------------

def test_low_stock_empty():
    inv = Inventory()
    assert inv.low_stock() == []


def test_low_stock_includes_threshold_boundary():
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


def test_low_stock_excludes_above_threshold():
    inv = Inventory(threshold=2)
    inv.add_item("a", 3, 1.0)
    assert inv.low_stock() == []


# ---------------------------------------------------------------------------
# apply_discount
# ---------------------------------------------------------------------------

def test_apply_discount_basic():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    new_price = inv.apply_discount("widget", 10)
    assert new_price == pytest.approx(9.0)
    assert inv.inventory_report()[0]["price"] == pytest.approx(9.0)


def test_apply_discount_zero_percent():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    assert inv.apply_discount("widget", 0) == pytest.approx(10.0)


def test_apply_discount_hundred_percent():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    assert inv.apply_discount("widget", 100) == pytest.approx(0.0)


def test_apply_discount_capped_at_fifty_percent():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    assert inv.apply_discount("widget", 80) == pytest.approx(5.0)


def test_apply_discount_exactly_fifty_percent():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    assert inv.apply_discount("widget", 50) == pytest.approx(5.0)


def test_apply_discount_rounds_to_two_decimals():
    inv = Inventory()
    inv.add_item("widget", 1, 9.99)
    result = inv.apply_discount("widget", 33)
    assert result == pytest.approx(round(9.99 * 0.67, 2))


def test_apply_discount_negative_percent_raises():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("widget", -1)


def test_apply_discount_over_hundred_raises():
    inv = Inventory()
    inv.add_item("widget", 1, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("widget", 100.01)


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

def test_bulk_restock_restocks_known_items():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    inv.add_item("b", 1, 1.0)
    missing = inv.bulk_restock({"a": 2, "b": 3})
    assert missing == []
    assert inv.stock_level("a") == 3
    assert inv.stock_level("b") == 4


def test_bulk_restock_returns_missing_names():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    missing = inv.bulk_restock({"a": 1, "ghost": 5})
    assert missing == ["ghost"]
    assert inv.stock_level("a") == 2


def test_bulk_restock_ignores_non_positive_quantities():
    inv = Inventory()
    inv.add_item("a", 1, 1.0)
    inv.bulk_restock({"a": 0, "a2": -3})
    assert inv.stock_level("a") == 1


def test_bulk_restock_empty_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.bulk_restock({})


def test_bulk_restock_name_normalized():
    inv = Inventory()
    inv.add_item("Widget", 1, 1.0)
    missing = inv.bulk_restock({"  WIDGET ": 2})
    assert missing == []
    assert inv.stock_level("widget") == 3


# ---------------------------------------------------------------------------
# inventory_report
# ---------------------------------------------------------------------------

def test_inventory_report_empty():
    inv = Inventory()
    assert inv.inventory_report() == []


def test_inventory_report_structure():
    inv = Inventory()
    inv.add_item("widget", 2, 3.0)
    rows = inv.inventory_report()
    assert len(rows) == 1
    row = rows[0]
    assert row["name"] == "widget"
    assert row["quantity"] == pytest.approx(2.0)
    assert row["price"] == pytest.approx(3.0)
    assert row["value"] == pytest.approx(6.0)


def test_inventory_report_sorted_by_descending_value():
    inv = Inventory()
    inv.add_item("low", 1, 1.0)
    inv.add_item("high", 10, 5.0)
    inv.add_item("mid", 2, 3.0)
    names = [row["name"] for row in inv.inventory_report()]
    assert names == ["high", "mid", "low"]


def test_inventory_report_ties_sorted_by_name():
    inv = Inventory()
    inv.add_item("beta", 1, 2.0)
    inv.add_item("alpha", 2, 1.0)
    names = [row["name"] for row in inv.inventory_report()]
    assert names == ["alpha", "beta"]


def test_inventory_report_value_rounded():
    inv = Inventory()
    inv.add_item("a", 3, 0.333)
    row = inv.inventory_report()[0]
    assert row["value"] == pytest.approx(1.0)
