"""M5 - Medium-high inventory management (target complexity 5-8).

A small in-memory inventory built on dictionaries and nested loops.  It mixes
stock mutations, reorder thresholds, percentage discounts and a valuation
report, giving generated suites several partially-overlapping behaviours to
exercise.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "DEFAULT_THRESHOLD",
    "Inventory",
]

#: Default quantity below which an item is considered low on stock.
DEFAULT_THRESHOLD: Final[int] = 5


class Inventory:
    """A dictionary-backed inventory of named items.

    Each entry stores ``{"quantity": int, "price": float}``.  All mutating
    methods reject negative quantities and unknown item names early, which
    keeps the failure modes explicit for test generation.
    """

    def __init__(self, threshold: int = DEFAULT_THRESHOLD) -> None:
        if threshold < 0:
            raise ValueError("threshold must be non-negative")
        self._items: dict[str, dict[str, float]] = {}
        self._threshold = threshold

    def add_item(self, name: str, quantity: int, price: float) -> None:
        """Add ``quantity`` units of ``name`` at ``price`` per unit.

        Existing items keep their old price and accumulate quantity.  A new
        item is created when ``name`` is not present.

        Raises:
            ValueError: If ``quantity`` is negative or ``price`` is negative
                or ``name`` is blank.
        """
        self._validate_purchase(name, quantity, price)
        key = name.strip().lower()
        existing = self._items.get(key)
        if existing is None:
            self._items[key] = {"quantity": float(quantity), "price": float(price)}
            return
        existing["quantity"] += quantity
        if price > 0 and price < existing["price"]:
            existing["price"] = float(price)

    @staticmethod
    def _validate_purchase(name: str, quantity: int, price: float) -> None:
        """Validate the arguments shared by :meth:`add_item` and restocks."""
        if not isinstance(name, str) or not name.strip():
            raise ValueError("item name must not be blank")
        if quantity < 0:
            raise ValueError("quantity must be non-negative")
        if price < 0:
            raise ValueError("price must be non-negative")

    def remove_item(self, name: str, quantity: int) -> None:
        """Remove ``quantity`` units of ``name``.

        Raises:
            KeyError: If ``name`` is unknown.
            ValueError: If ``quantity`` is negative or exceeds available stock.
        """
        if quantity < 0:
            raise ValueError("quantity must be non-negative")
        key = name.strip().lower()
        if key not in self._items:
            raise KeyError(name)
        available = int(self._items[key]["quantity"])
        if quantity > available:
            raise ValueError("cannot remove more than available stock")
        self._items[key]["quantity"] = float(available - quantity)
        if self._items[key]["quantity"] == 0:
            self._items[key]["price"] = max(self._items[key]["price"], 0.0)

    def restock(self, name: str, quantity: int) -> int:
        """Add stock without changing the recorded unit price.

        Raises:
            KeyError: If ``name`` is unknown.
            ValueError: If ``quantity`` is not positive.
        """
        if quantity <= 0:
            raise ValueError("restock quantity must be positive")
        key = name.strip().lower()
        if key not in self._items:
            raise KeyError(name)
        self._items[key]["quantity"] += quantity
        return int(self._items[key]["quantity"])

    def stock_level(self, name: str) -> int:
        """Return the current stock for ``name``.

        Raises:
            KeyError: If ``name`` is unknown.
        """
        key = name.strip().lower()
        if key not in self._items:
            raise KeyError(name)
        return int(self._items[key]["quantity"])

    def total_value(self) -> float:
        """Return the sum of ``quantity * price`` over every item."""
        total = 0.0
        for record in self._items.values():
            total += record["quantity"] * record["price"]
        return round(total, 2)

    def low_stock(self) -> list[str]:
        """Return the names of items at or below the reorder threshold.

        Items with zero quantity come first, then alphabetical order.
        """
        low: list[str] = []
        for name, record in self._items.items():
            if record["quantity"] <= self._threshold:
                low.append(name)
        return sorted(low, key=lambda item: (self._items[item]["quantity"], item))

    def apply_discount(self, name: str, percent: float) -> float:
        """Apply a percentage discount to ``name`` and return the new price.

        The price is rounded to two decimals and can never become negative.
        Discounts above 50 % are capped at 50 % so clearance sales stay sane.

        Raises:
            KeyError: If ``name`` is unknown.
            ValueError: If ``percent`` is outside ``[0, 100]``.
        """
        if percent < 0 or percent > 100:
            raise ValueError("percent must be between 0 and 100")
        key = name.strip().lower()
        if key not in self._items:
            raise KeyError(name)
        effective = 50.0 if percent > 50 else percent
        old_price = self._items[key]["price"]
        new_price = max(0.0, round(old_price * (1 - effective / 100), 2))
        self._items[key]["price"] = new_price
        return new_price

    def bulk_restock(self, order: dict[str, int]) -> list[str]:
        """Restock several items at once; return the names that were unknown.

        Unknown names are skipped rather than aborting the whole order, so a
        partial delivery can still be recorded.  Non-positive quantities are
        ignored.

        Raises:
            ValueError: If ``order`` is empty.
        """
        if not order:
            raise ValueError("restock order must not be empty")
        missing: list[str] = []
        for name, quantity in order.items():
            key = name.strip().lower()
            if key not in self._items:
                missing.append(name)
            elif quantity > 0:
                self._items[key]["quantity"] += quantity
        return missing

    def inventory_report(self) -> list[dict[str, float | str]]:
        """Return one row per item, sorted by descending total value.

        Each row has ``name``, ``quantity``, ``price`` and ``value`` keys.
        """
        rows: list[dict[str, float | str]] = []
        for name, record in self._items.items():
            rows.append(
                {
                    "name": name,
                    "quantity": record["quantity"],
                    "price": record["price"],
                    "value": round(record["quantity"] * record["price"], 2),
                }
            )
        rows.sort(key=lambda row: (-float(row["value"]), str(row["name"])))
        return rows
