import pytest

from benchmark.m5_inventory import DEFAULT_THRESHOLD, Inventory


def test_default_threshold_value():
    assert DEFAULT_THRESHOLD == 5


def test_init_default_threshold():
    inv = Inventory()
    assert inv._threshold == DEFAULT_THRESHOLD


def test_init_custom_threshold():
    inv = Inventory(threshold=10)
    assert inv._threshold == 10


def test_init_zero_threshold():
    inv = Inventory(threshold=0)
    assert inv._threshold == 0


def test_init_negative_threshold_raises():
    with pytest.raises(ValueError):
        Inventory(threshold=-1)


def test_add_item_new():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.5)
    assert inv.stock_level("Apple") == 10


def test_add_item_accumulates_quantity():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.5)
    inv.add_item("Apple", 5, 1.5)
    assert inv.stock_level("Apple") == 15


def test_add_item_keeps_old_price_when_higher():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.5)
    inv.add_item("Apple", 5, 2.0)
    assert inv.inventory_report()[0]["price"] == pytest.approx(1.5)


def test_add_item_lowers_price_when_cheaper():
    inv = Inventory()
    inv.add_item("Apple", 10, 2.0)
    inv.add_item("Apple", 5, 1.5)
    assert inv.inventory_report()[0]["price"] == pytest.approx(1.5)


def test_add_item_zero_price_does_not_change_price():
    inv = Inventory()
    inv.add_item("Apple", 10, 2.0)
    inv.add_item("Apple", 5, 0.0)
    assert inv.inventory_report()[0]["price"] == pytest.approx(2.0)


def test_add_item_normalizes_name():
    inv = Inventory()
    inv.add_item("  Apple  ", 10, 1.0)
    assert inv.stock_level("apple") == 10
    assert inv.stock_level("APPLE") == 10


def test_add_item_zero_quantity():
    inv = Inventory()
    inv.add_item("Apple", 0, 1.0)
    assert inv.stock_level("Apple") == 0


def test_add_item_negative_quantity_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("Apple", -1, 1.0)


def test_add_item_negative_price_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("Apple", 1, -1.0)


def test_add_item_blank_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("   ", 1, 1.0)


def test_add_item_empty_name_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.add_item("", 1, 1.0)


def test_remove_item_basic():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.remove_item("Apple", 4)
    assert inv.stock_level("Apple") == 6


def test_remove_item_all():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.remove_item("Apple", 10)
    assert inv.stock_level("Apple") == 0


def test_remove_item_zero():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.remove_item("Apple", 0)
    assert inv.stock_level("Apple") == 10


def test_remove_item_negative_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("Apple", -1)


def test_remove_item_unknown_raises():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.remove_item("Banana", 1)


def test_remove_item_too_many_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    with pytest.raises(ValueError):
        inv.remove_item("Apple", 11)


def test_remove_item_normalizes_name():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.remove_item("  APPLE ", 3)
    assert inv.stock_level("apple") == 7


def test_restock_basic():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    result = inv.restock("Apple", 5)
    assert result == 15
    assert inv.stock_level("Apple") == 15


def test_restock_does_not_change_price():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.restock("Apple", 5)
    assert inv.inventory_report()[0]["price"] == pytest.approx(1.0)


def test_restock_zero_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    with pytest.raises(ValueError):
        inv.restock("Apple", 0)


def test_restock_negative_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    with pytest.raises(ValueError):
        inv.restock("Apple", -5)


def test_restock_unknown_raises():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.restock("Banana", 5)


def test_stock_level_unknown_raises():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.stock_level("Banana")


def test_total_value_empty():
    inv = Inventory()
    assert inv.total_value() == pytest.approx(0.0)


def test_total_value_multiple_items():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.5)
    inv.add_item("Banana", 4, 2.25)
    assert inv.total_value() == pytest.approx(24.0)


def test_total_value_rounding():
    inv = Inventory()
    inv.add_item("Apple", 3, 0.333)
    assert inv.total_value() == pytest.approx(1.0)


def test_low_stock_empty():
    inv = Inventory()
    assert inv.low_stock() == []


def test_low_stock_threshold_boundary():
    inv = Inventory(threshold=5)
    inv.add_item("Apple", 5, 1.0)
    inv.add_item("Banana", 6, 1.0)
    assert inv.low_stock() == ["apple"]


def test_low_stock_zero_first_then_alpha():
    inv = Inventory(threshold=5)
    inv.add_item("Banana", 0, 1.0)
    inv.add_item("Apple", 0, 1.0)
    inv.add_item("Cherry", 3, 1.0)
    assert inv.low_stock() == ["apple", "banana", "cherry"]


def test_low_stock_sorted_by_quantity_then_name():
    inv = Inventory(threshold=5)
    inv.add_item("Zebra", 2, 1.0)
    inv.add_item("Apple", 2, 1.0)
    inv.add_item("Mango", 1, 1.0)
    assert inv.low_stock() == ["mango", "apple", "zebra"]


def test_apply_discount_basic():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    new_price = inv.apply_discount("Apple", 10)
    assert new_price == pytest.approx(9.0)


def test_apply_discount_zero():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    new_price = inv.apply_discount("Apple", 0)
    assert new_price == pytest.approx(10.0)


def test_apply_discount_hundred():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    new_price = inv.apply_discount("Apple", 100)
    assert new_price == pytest.approx(5.0)


def test_apply_discount_capped_at_fifty():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    new_price = inv.apply_discount("Apple", 80)
    assert new_price == pytest.approx(5.0)


def test_apply_discount_rounding():
    inv = Inventory()
    inv.add_item("Apple", 10, 9.99)
    new_price = inv.apply_discount("Apple", 33)
    assert new_price == pytest.approx(6.69)


def test_apply_discount_negative_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("Apple", -1)


def test_apply_discount_over_hundred_raises():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    with pytest.raises(ValueError):
        inv.apply_discount("Apple", 101)


def test_apply_discount_unknown_raises():
    inv = Inventory()
    with pytest.raises(KeyError):
        inv.apply_discount("Banana", 10)


def test_apply_discount_normalizes_name():
    inv = Inventory()
    inv.add_item("Apple", 10, 10.0)
    new_price = inv.apply_discount("  APPLE ", 10)
    assert new_price == pytest.approx(9.0)


def test_bulk_restock_basic():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.add_item("Banana", 5, 1.0)
    missing = inv.bulk_restock({"Apple": 5, "Banana": 3})
    assert missing == []
    assert inv.stock_level("Apple") == 15
    assert inv.stock_level("Banana") == 8


def test_bulk_restock_missing_items():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    missing = inv.bulk_restock({"Apple": 5, "Cherry": 3})
    assert missing == ["Cherry"]
    assert inv.stock_level("Apple") == 15


def test_bulk_restock_ignores_non_positive():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.bulk_restock({"Apple": 0, "Banana": -5})
    assert inv.stock_level("Apple") == 10


def test_bulk_restock_empty_raises():
    inv = Inventory()
    with pytest.raises(ValueError):
        inv.bulk_restock({})


def test_bulk_restock_normalizes_names():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    missing = inv.bulk_restock({"  APPLE ": 5})
    assert missing == []
    assert inv.stock_level("apple") == 15


def test_inventory_report_empty():
    inv = Inventory()
    assert inv.inventory_report() == []


def test_inventory_report_sorted_by_value_desc():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.0)
    inv.add_item("Banana", 5, 5.0)
    inv.add_item("Cherry", 2, 1.0)
    report = inv.inventory_report()
    assert [row["name"] for row in report] == ["banana", "apple", "cherry"]


def test_inventory_report_tie_break_by_name():
    inv = Inventory()
    inv.add_item("Banana", 10, 1.0)
    inv.add_item("Apple", 10, 1.0)
    report = inv.inventory_report()
    assert [row["name"] for row in report] == ["apple", "banana"]


def test_inventory_report_row_contents():
    inv = Inventory()
    inv.add_item("Apple", 10, 1.5)
    report = inv.inventory_report()
    assert len(report) == 1
    row = report[0]
    assert row["name"] == "apple"
    assert row["quantity"] == pytest.approx(10.0)
    assert row["price"] == pytest.approx(1.5)
    assert row["value"] == pytest.approx(15.0)
