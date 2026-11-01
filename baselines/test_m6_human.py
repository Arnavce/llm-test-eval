"""Human ground-truth tests for :mod:`benchmark.m6_bank_account` (baseline M6)."""

from __future__ import annotations

import pytest

from benchmark.m6_bank_account import MIN_DEPOSIT, OVERDRAFT_FEE, BankAccount


# ---------------------------------------------------------------------------
# Construction and validation
# ---------------------------------------------------------------------------
def test_new_account_starts_empty() -> None:
    account = BankAccount("Ada")
    assert account.owner == "Ada"
    assert account.balance == 0.0
    assert account.closed is False
    assert account.transactions() == []


def test_owner_is_stripped() -> None:
    assert BankAccount("  Grace  ").owner == "Grace"


@pytest.mark.parametrize("bad_owner", ["", "   "])
def test_blank_owner_is_rejected(bad_owner: str) -> None:
    with pytest.raises(ValueError, match="owner"):
        BankAccount(bad_owner)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"overdraft_limit": -1},
        {"monthly_fee": -0.01},
        {"interest_rate": -0.001},
    ],
)
def test_negative_constructor_arguments_are_rejected(kwargs: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        BankAccount("Ada", **kwargs)


# ---------------------------------------------------------------------------
# Deposits
# ---------------------------------------------------------------------------
def test_deposit_increases_balance() -> None:
    account = BankAccount("Ada")
    assert account.deposit(50.0) == 50.0


def test_deposit_minimum_is_inclusive() -> None:
    account = BankAccount("Ada")
    assert account.deposit(MIN_DEPOSIT) == MIN_DEPOSIT


@pytest.mark.parametrize("amount", [0.0, -5.0, 0.99])
def test_deposit_below_minimum_is_rejected(amount: float) -> None:
    account = BankAccount("Ada")
    with pytest.raises(ValueError, match="at least"):
        account.deposit(amount)


def test_deposit_logs_a_transaction() -> None:
    account = BankAccount("Ada")
    account.deposit(25.0)
    entries = account.transactions()
    assert len(entries) == 1
    assert entries[0]["type"] == "deposit"
    assert entries[0]["amount"] == 25.0
    assert entries[0]["balance"] == 25.0


def test_transactions_returns_a_copy() -> None:
    account = BankAccount("Ada")
    account.deposit(25.0)
    snapshot = account.transactions()
    snapshot.pop()
    assert len(account.transactions()) == 1


# ---------------------------------------------------------------------------
# Withdrawals, fees and overdraft
# ---------------------------------------------------------------------------
def test_simple_withdrawal() -> None:
    account = BankAccount("Ada")
    account.deposit(100.0)
    assert account.withdraw(40.0) == 60.0


def test_withdrawal_at_fee_free_limit_has_no_fee() -> None:
    account = BankAccount("Ada")
    account.deposit(200.0)
    assert account.withdraw(100.0) == 100.0


def test_withdrawal_above_limit_charges_monthly_fee() -> None:
    account = BankAccount("Ada", monthly_fee=2.5)
    account.deposit(200.0)
    assert account.withdraw(150.0) == 47.5


def test_partial_overdraft_incurs_flat_fee() -> None:
    account = BankAccount("Ada", overdraft_limit=100.0, monthly_fee=0.0)
    assert account.withdraw(50.0) == -(50.0 + OVERDRAFT_FEE)


def test_overdraft_beyond_limit_is_rejected() -> None:
    account = BankAccount("Ada", overdraft_limit=30.0)
    account.deposit(10.0)
    with pytest.raises(ValueError, match="insufficient funds"):
        account.withdraw(45.0)
    assert account.balance == 10.0


def test_overdraft_fee_pushing_past_limit_is_rejected() -> None:
    account = BankAccount("Ada", overdraft_limit=OVERDRAFT_FEE, monthly_fee=0.0)
    with pytest.raises(ValueError, match="overdraft fee"):
        account.withdraw(1.0)
    assert account.balance == 0.0


@pytest.mark.parametrize("amount", [0.0, -1.0])
def test_non_positive_withdrawal_is_rejected(amount: float) -> None:
    account = BankAccount("Ada")
    account.deposit(10.0)
    with pytest.raises(ValueError, match="positive"):
        account.withdraw(amount)


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------
def test_transfer_moves_money_between_accounts() -> None:
    alice = BankAccount("Alice")
    bob = BankAccount("Bob")
    alice.deposit(100.0)
    alice.transfer(bob, 40.0)
    assert alice.balance == 60.0
    assert bob.balance == 40.0


def test_transfer_is_logged_on_both_accounts() -> None:
    alice = BankAccount("Alice")
    bob = BankAccount("Bob")
    alice.deposit(100.0)
    alice.transfer(bob, 40.0)
    kinds = [entry["type"] for entry in alice.transactions()]
    assert "withdraw" in kinds
    assert "deposit" in [entry["type"] for entry in bob.transactions()]


def test_transfer_to_non_account_is_rejected() -> None:
    account = BankAccount("Ada")
    account.deposit(10.0)
    with pytest.raises(ValueError, match="BankAccount"):
        account.transfer("not an account", 5.0)  # type: ignore[arg-type]


def test_transfer_non_positive_amount_is_rejected() -> None:
    account = BankAccount("Ada")
    other = BankAccount("Bob")
    account.deposit(10.0)
    with pytest.raises(ValueError, match="positive"):
        account.transfer(other, 0)


# ---------------------------------------------------------------------------
# Interest, closing and summary
# ---------------------------------------------------------------------------
def test_interest_is_credited_on_positive_balance() -> None:
    account = BankAccount("Ada", interest_rate=0.01)
    account.deposit(1000.0)
    assert account.apply_monthly_interest() == 1010.0


def test_interest_on_zero_balance_is_noop() -> None:
    account = BankAccount("Ada", interest_rate=0.05)
    assert account.apply_monthly_interest() == 0.0
    assert account.transactions() == []


def test_zero_interest_rate_is_noop() -> None:
    account = BankAccount("Ada", interest_rate=0.0)
    account.deposit(100.0)
    assert account.apply_monthly_interest() == 100.0
    assert len(account.transactions()) == 1


def test_close_requires_zero_balance() -> None:
    account = BankAccount("Ada")
    account.deposit(5.0)
    with pytest.raises(ValueError, match="zero"):
        account.close()
    assert account.closed is False


def test_close_and_then_operate_is_rejected() -> None:
    account = BankAccount("Ada")
    account.close()
    assert account.closed is True
    with pytest.raises(ValueError, match="closed"):
        account.close()
    with pytest.raises(ValueError, match="closed"):
        account.deposit(10.0)


def test_summary_snapshot() -> None:
    account = BankAccount("Ada", overdraft_limit=50.0)
    account.deposit(20.0)
    summary = account.summary()
    assert summary["owner"] == "Ada"
    assert summary["balance"] == 20.0
    assert summary["transactions"] == 1
    assert summary["closed"] is False


# ---------------------------------------------------------------------------
# Monthly statements, disputes and history filters
# ---------------------------------------------------------------------------
def test_monthly_statement_credits_interest_and_waives_fee() -> None:
    account = BankAccount("Ada", interest_rate=0.01, monthly_fee=2.5)
    account.deposit(1000.0)
    statement = account.apply_monthly_statement()
    assert statement["open_balance"] == 1000.0
    assert statement["interest"] == 10.0
    assert statement["fee"] == 0.0
    assert statement["close_balance"] == 1010.0


def test_monthly_statement_charges_fee_on_small_balance() -> None:
    account = BankAccount("Ada", monthly_fee=2.5)
    account.deposit(3.0)
    statement = account.apply_monthly_statement()
    assert statement["fee"] == 2.5
    assert statement["close_balance"] == 0.5


def test_monthly_statement_fee_overflowing_overdraft_raises() -> None:
    account = BankAccount("Ada", monthly_fee=10.0, overdraft_limit=1.0)
    with pytest.raises(ValueError, match="monthly fee"):
        account.apply_monthly_statement()
    assert account.balance == 0.0


def test_monthly_statement_on_closed_account_raises() -> None:
    account = BankAccount("Ada")
    account.close()
    with pytest.raises(ValueError, match="closed"):
        account.apply_monthly_statement()


def test_dispute_refunds_a_withdrawal() -> None:
    account = BankAccount("Ada")
    account.deposit(100.0)
    account.withdraw(40.0)
    assert account.dispute(1, 40.0) == 100.0


def test_dispute_only_allows_debits() -> None:
    account = BankAccount("Ada")
    account.deposit(100.0)
    with pytest.raises(ValueError, match="debit"):
        account.dispute(0, 10.0)


def test_dispute_rejects_double_claims_and_bad_amounts() -> None:
    account = BankAccount("Ada")
    account.deposit(100.0)
    account.withdraw(40.0)
    account.dispute(1, 10.0)
    with pytest.raises(ValueError, match="exceed"):
        account.dispute(1, 10_000.0)
    with pytest.raises(ValueError, match="already disputed"):
        account.dispute(1, 5.0)


def test_dispute_rejects_bad_index() -> None:
    account = BankAccount("Ada")
    with pytest.raises(ValueError, match="out of range"):
        account.dispute(0, 1.0)


def test_transaction_history_filters_by_kind() -> None:
    account = BankAccount("Ada", monthly_fee=2.5)
    account.deposit(300.0)
    account.withdraw(150.0)
    account.withdraw(50.0)
    account.withdraw(120.0)
    assert len(account.transaction_history("withdraw")) == 3
    assert len(account.transaction_history("fee")) == 1
    assert account.transaction_history("interest") == []


def test_transaction_history_rejects_unknown_kind() -> None:
    account = BankAccount("Ada")
    with pytest.raises(ValueError, match="unknown transaction kind"):
        account.transaction_history("gift")


def test_summary_reports_disputes() -> None:
    account = BankAccount("Ada")
    account.deposit(20.0)
    account.withdraw(10.0)
    account.dispute(1, 5.0)
    assert account.summary()["disputes"] == 1
