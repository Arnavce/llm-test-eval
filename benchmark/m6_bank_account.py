"""M6 - High-complexity bank account state machine (target complexity 6-10).

The most demanding module in the CPB-6 corpus.  A :class:`BankAccount`
enforces a deposit/withdraw state machine with fee schedules, overdraft limits,
transaction logs, interest and dispute handling.  Every guard has an observable
consequence, which gives mutation testing many independent behaviours to probe.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "MIN_DEPOSIT",
    "OVERDRAFT_FEE",
    "BankAccount",
]

#: Smallest deposit the bank accepts.
MIN_DEPOSIT: Final[float] = 1.0

#: Flat fee charged whenever the overdraft facility is used.
OVERDRAFT_FEE: Final[float] = 10.0

#: Fixed-point precision for balances.
PRECISION: Final[int] = 2

#: Transaction kinds that move money out of the account.
_DEBIT_TYPES: Final[frozenset[str]] = frozenset({"withdraw", "transfer_out", "fee"})


class BankAccount:
    """A checking account with fees, overdraft protection and a transaction log.

    Args:
        owner: Non-empty account holder name.
        overdraft_limit: Maximum negative balance allowed (default ``100``).
        monthly_fee: Fee charged on every withdrawal above ``FEE_FREE_LIMIT``.
        interest_rate: Monthly interest rate as a fraction (``0.01`` = 1%).

    Raises:
        ValueError: If ``owner`` is blank or any numeric argument is negative.
    """

    FEE_FREE_LIMIT: Final[float] = 100.0
    MONTHLY_FEE: Final[float] = 2.5

    def __init__(
        self,
        owner: str,
        overdraft_limit: float = 100.0,
        monthly_fee: float = MONTHLY_FEE,
        interest_rate: float = 0.0,
    ) -> None:
        if not isinstance(owner, str) or not owner.strip():
            raise ValueError("owner must not be blank")
        if overdraft_limit < 0:
            raise ValueError("overdraft_limit must be non-negative")
        if monthly_fee < 0:
            raise ValueError("monthly_fee must be non-negative")
        if interest_rate < 0:
            raise ValueError("interest_rate must be non-negative")
        self.owner: Final[str] = owner.strip()
        self.overdraft_limit = float(overdraft_limit)
        self.monthly_fee = float(monthly_fee)
        self.interest_rate = float(interest_rate)
        self._balance = 0.0
        self._log: list[dict[str, float | str]] = []
        self._closed = False
        self._disputed: set[int] = set()

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------
    @property
    def balance(self) -> float:
        """Current balance, rounded to cents."""
        return round(self._balance, PRECISION)

    @property
    def closed(self) -> bool:
        """Whether :meth:`close` has been called."""
        return self._closed

    def transactions(self) -> list[dict[str, float | str]]:
        """Return a copy of the transaction log, oldest first."""
        return [dict(entry) for entry in self._log]

    # ------------------------------------------------------------------
    # Mutating operations
    # ------------------------------------------------------------------
    def deposit(self, amount: float) -> float:
        """Deposit ``amount`` and return the new balance.

        Raises:
            ValueError: If the account is closed or ``amount < MIN_DEPOSIT``.
        """
        self._ensure_open()
        if amount < MIN_DEPOSIT:
            raise ValueError(f"deposit must be at least {MIN_DEPOSIT:.2f}")
        self._balance += amount
        self._record("deposit", amount)
        return self.balance

    def withdraw(self, amount: float) -> float:
        """Withdraw ``amount``, charging fees where applicable.

        A fee equal to :attr:`monthly_fee` is applied when ``amount`` exceeds
        :attr:`FEE_FREE_LIMIT`.  If the resulting balance would fall below
        ``-overdraft_limit`` the withdrawal fails, but a partial overdraft is
        allowed and incurs a flat :data:`OVERDRAFT_FEE`.

        Raises:
            ValueError: If the account is closed, ``amount`` is not positive,
                or the overdraft limit would be exceeded.
        """
        self._ensure_open()
        if amount <= 0:
            raise ValueError("withdrawal amount must be positive")
        fee = 0.0
        if amount > self.FEE_FREE_LIMIT:
            fee = self.monthly_fee
        projected = self._balance - amount - fee
        if projected < -self.overdraft_limit:
            raise ValueError("insufficient funds: overdraft limit exceeded")
        overdraft_fee = 0.0
        if projected < 0:
            overdraft_fee = OVERDRAFT_FEE
            if projected - overdraft_fee < -self.overdraft_limit:
                raise ValueError("insufficient funds: overdraft fee not covered")
        self._balance = projected
        self._record("withdraw", amount)
        if overdraft_fee > 0:
            self._balance -= overdraft_fee
            self._record("fee", overdraft_fee)
        return self.balance

    def transfer(self, other: "BankAccount", amount: float) -> float:
        """Transfer ``amount`` to ``other`` and return this account's balance.

        Raises:
            ValueError: If either account is closed, ``other`` is not a
                :class:`BankAccount`, ``other`` is the same object, or
                ``amount`` is not positive.
        """
        self._ensure_open()
        if not isinstance(other, BankAccount):
            raise ValueError("transfer target must be a BankAccount")
        if other is self:
            raise ValueError("cannot transfer to the same account")
        other._ensure_open()
        if amount <= 0:
            raise ValueError("transfer amount must be positive")
        self.withdraw(amount)
        other.deposit(amount)
        return self.balance

    def apply_monthly_interest(self) -> float:
        """Credit interest on a positive balance and return the new balance.

        A closed account or a zero/negative balance earns nothing, so no
        transaction is logged in those cases.
        """
        self._ensure_open()
        if self._balance <= 0 or self.interest_rate == 0:
            return self.balance
        earned = round(self._balance * self.interest_rate, PRECISION)
        self._balance += earned
        self._record("interest", earned)
        return self.balance

    def apply_monthly_statement(self) -> dict[str, float]:
        """Apply interest and the maintenance fee for one statement period.

        The fee is waived when the closing balance is at least twice the
        monthly fee; interest is only credited on a positive balance.  Returns
        a breakdown of ``open_balance``, ``interest``, ``fee`` and
        ``close_balance``.

        Raises:
            ValueError: If the account is closed.
        """
        self._ensure_open()
        opening = self.balance
        interest = self._credit_interest_for_statement()
        fee = self._charge_maintenance_fee()
        return {
            "open_balance": opening,
            "interest": interest,
            "fee": fee,
            "close_balance": self.balance,
        }

    def _credit_interest_for_statement(self) -> float:
        """Credit this period's interest and return the amount earned."""
        if self._balance <= 0 or self.interest_rate <= 0:
            return 0.0
        earned = round(self._balance * self.interest_rate, PRECISION)
        self._balance += earned
        self._record("interest", earned)
        return earned

    def _charge_maintenance_fee(self) -> float:
        """Charge the maintenance fee unless the balance is comfortably positive."""
        if self._balance >= 2 * self.monthly_fee:
            return 0.0
        fee = self.monthly_fee
        if fee <= 0:
            return 0.0
        if self._balance - fee < -self.overdraft_limit:
            raise ValueError("monthly fee would exceed the overdraft limit")
        self._balance -= fee
        self._record("fee", fee)
        return fee

    def dispute(self, index: int, amount: float) -> float:
        """Reverse the transaction at ``index`` by refunding ``amount``.

        Only debit transactions can be disputed, each one once, and the
        refund may not exceed the original amount.

        Raises:
            ValueError: If the account is closed, ``index`` is out of range,
                the transaction is not a debit, the refund is not positive,
                the refund exceeds the original, or the transaction was
                already disputed.
        """
        self._ensure_open()
        if index < 0 or index >= len(self._log):
            raise ValueError("transaction index out of range")
        entry = self._log[index]
        if str(entry["type"]) not in _DEBIT_TYPES:
            raise ValueError("only debit transactions can be disputed")
        original = float(entry["amount"])
        if amount <= 0:
            raise ValueError("dispute amount must be positive")
        if amount > original:
            raise ValueError("dispute exceeds the original transaction")
        if index in self._disputed:
            raise ValueError("transaction already disputed")
        self._balance += amount
        self._disputed.add(index)
        self._record("refund", amount)
        return self.balance

    def transaction_history(self, kind: str | None = None) -> list[dict[str, float | str]]:
        """Return transactions, optionally filtered by ``kind``.

        Raises:
            ValueError: If ``kind`` is provided and not a known transaction type.
        """
        known = {
            "deposit",
            "withdraw",
            "transfer_out",
            "interest",
            "fee",
            "refund",
            "close",
        }
        if kind is not None and kind not in known:
            raise ValueError(f"unknown transaction kind: {kind!r}")
        if kind is None:
            return self.transactions()
        return [dict(entry) for entry in self._log if entry["type"] == kind]

    def close(self) -> None:
        """Close the account.

        Raises:
            ValueError: If the account is already closed or the balance is not
                exactly zero.
        """
        if self._closed:
            raise ValueError("account is already closed")
        if self.balance != 0:
            raise ValueError("account balance must be zero before closing")
        self._record("close", 0.0)
        self._closed = True

    def summary(self) -> dict[str, float | int | str | bool]:
        """Return a compact snapshot of the account state."""
        return {
            "owner": self.owner,
            "balance": self.balance,
            "overdraft_limit": self.overdraft_limit,
            "closed": self._closed,
            "transactions": len(self._log),
            "disputes": len(self._disputed),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_open(self) -> None:
        """Raise ``ValueError`` when the account is closed."""
        if self._closed:
            raise ValueError("account is closed")

    def _record(self, kind: str, amount: float) -> None:
        """Append a normalised transaction record to the log."""
        self._log.append(
            {
                "type": kind,
                "amount": round(float(amount), PRECISION),
                "balance": self.balance,
            }
        )
