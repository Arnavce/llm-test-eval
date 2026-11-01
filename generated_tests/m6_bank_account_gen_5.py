import pytest

from benchmark.m6_bank_account import (
    MIN_DEPOSIT,
    OVERDRAFT_FEE,
    BankAccount,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
def test_constants():
    assert MIN_DEPOSIT == 1.0
    assert OVERDRAFT_FEE == 10.0


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------
def test_constructor_defaults():
    acc = BankAccount("Alice")
    assert acc.owner == "Alice"
    assert acc.overdraft_limit == 100.0
    assert acc.monthly_fee == BankAccount.MONTHLY_FEE
    assert acc.interest_rate == 0.0
    assert acc.balance == 0.0
    assert acc.closed is False
    assert acc.transactions() == []


def test_constructor_strips_owner():
    acc = BankAccount("  Bob  ")
    assert acc.owner == "Bob"


def test_constructor_custom_values():
    acc = BankAccount("Carol", overdraft_limit=50, monthly_fee=1.5, interest_rate=0.02)
    assert acc.overdraft_limit == 50.0
    assert acc.monthly_fee == 1.5
    assert acc.interest_rate == 0.02


@pytest.mark.parametrize("owner", ["", "   ", "\t\n"])
def test_constructor_blank_owner(owner):
    with pytest.raises(ValueError):
        BankAccount(owner)


def test_constructor_non_string_owner():
    with pytest.raises(ValueError):
        BankAccount(None)  # type: ignore[arg-type]


def test_constructor_negative_overdraft():
    with pytest.raises(ValueError):
        BankAccount("X", overdraft_limit=-1)


def test_constructor_negative_monthly_fee():
    with pytest.raises(ValueError):
        BankAccount("X", monthly_fee=-0.01)


def test_constructor_negative_interest():
    with pytest.raises(ValueError):
        BankAccount("X", interest_rate=-0.01)


def test_constructor_zero_values_allowed():
    acc = BankAccount("X", overdraft_limit=0, monthly_fee=0, interest_rate=0)
    assert acc.overdraft_limit == 0.0
    assert acc.monthly_fee == 0.0
    assert acc.interest_rate == 0.0


# ---------------------------------------------------------------------------
# Deposit
# ---------------------------------------------------------------------------
def test_deposit_basic():
    acc = BankAccount("A")
    assert acc.deposit(50) == 50.0
    assert acc.balance == 50.0


def test_deposit_minimum_boundary():
    acc = BankAccount("A")
    assert acc.deposit(MIN_DEPOSIT) == MIN_DEPOSIT


def test_deposit_below_minimum():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.deposit(MIN_DEPOSIT - 0.01)


def test_deposit_negative():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.deposit(-5)


def test_deposit_records_transaction():
    acc = BankAccount("A")
    acc.deposit(20)
    log = acc.transactions()
    assert len(log) == 1
    assert log[0]["type"] == "deposit"
    assert log[0]["amount"] == 20.0
    assert log[0]["balance"] == 20.0


def test_deposit_rounds_balance():
    acc = BankAccount("A")
    acc.deposit(10.005)
    assert acc.balance == pytest.approx(10.01)


def test_deposit_on_closed_account():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.deposit(10)


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------
def test_withdraw_basic():
    acc = BankAccount("A")
    acc.deposit(100)
    assert acc.withdraw(40) == 60.0


def test_withdraw_zero():
    acc = BankAccount("A")
    acc.deposit(100)
    with pytest.raises(ValueError):
        acc.withdraw(0)


def test_withdraw_negative():
    acc = BankAccount("A")
    acc.deposit(100)
    with pytest.raises(ValueError):
        acc.withdraw(-1)


def test_withdraw_fee_free_limit_boundary():
    acc = BankAccount("A")
    acc.deposit(200)
    # exactly at limit -> no fee
    assert acc.withdraw(BankAccount.FEE_FREE_LIMIT) == pytest.approx(100.0)


def test_withdraw_above_fee_free_limit_charges_fee():
    acc = BankAccount("A")
    acc.deposit(200)
    result = acc.withdraw(BankAccount.FEE_FREE_LIMIT + 1)
    expected = 200 - (BankAccount.FEE_FREE_LIMIT + 1) - acc.monthly_fee
    assert result == pytest.approx(expected)


def test_withdraw_into_overdraft_charges_overdraft_fee():
    acc = BankAccount("A")
    acc.deposit(50)
    result = acc.withdraw(60)
    # projected = 50 - 60 = -10, overdraft fee 10 -> -20
    assert result == pytest.approx(-20.0)


def test_withdraw_overdraft_limit_exceeded():
    acc = BankAccount("A", overdraft_limit=10)
    acc.deposit(5)
    with pytest.raises(ValueError):
        acc.withdraw(20)


def test_withdraw_overdraft_fee_not_covered():
    acc = BankAccount("A", overdraft_limit=5)
    acc.deposit(10)
    # projected = 10 - 12 = -2, fee 10 -> -12 < -5
    with pytest.raises(ValueError):
        acc.withdraw(12)


def test_withdraw_records_fee_transaction():
    acc = BankAccount("A")
    acc.deposit(50)
    acc.withdraw(60)
    log = acc.transactions()
    types = [e["type"] for e in log]
    assert "withdraw" in types
    assert "fee" in types
    fee_entry = [e for e in log if e["type"] == "fee"][0]
    assert fee_entry["amount"] == OVERDRAFT_FEE


def test_withdraw_on_closed_account():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.withdraw(1)


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------
def test_transfer_basic():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    result = a.transfer(b, 30)
    assert result == pytest.approx(70.0)
    assert b.balance == pytest.approx(30.0)


def test_transfer_to_non_account():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer("not-an-account", 10)  # type: ignore[arg-type]


def test_transfer_to_self():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(a, 10)


def test_transfer_from_closed():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    a.close()
    with pytest.raises(ValueError):
        a.transfer(b, 10)


def test_transfer_to_closed():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    b.close()
    with pytest.raises(ValueError):
        a.transfer(b, 10)


def test_transfer_zero_amount():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(b, 0)


def test_transfer_negative_amount():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(b, -5)


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------
def test_interest_zero_balance():
    acc = BankAccount("A", interest_rate=0.05)
    assert acc.apply_monthly_interest() == 0.0
    assert acc.transactions() == []


def test_interest_zero_rate():
    acc = BankAccount("A", interest_rate=0.0)
    acc.deposit(100)
    assert acc.apply_monthly_interest() == 100.0
    assert len(acc.transactions()) == 1


def test_interest_positive():
    acc = BankAccount("A", interest_rate=0.10)
    acc.deposit(100)
    result = acc.apply_monthly_interest()
    assert result == pytest.approx(110.0)
    log = acc.transactions()
    assert log[-1]["type"] == "interest"
    assert log[-1]["amount"] == pytest.approx(10.0)


def test_interest_negative_balance():
    acc = BankAccount("A", interest_rate=0.10)
    acc.deposit(50)
    acc.withdraw(60)
    before = acc.balance
    assert acc.apply_monthly_interest() == before


def test_interest_on_closed():
    acc = BankAccount("A", interest_rate=0.10)
    acc.close()
    with pytest.raises(ValueError):
        acc.apply_monthly_interest()


# ---------------------------------------------------------------------------
# Monthly statement
# ---------------------------------------------------------------------------
def test_statement_interest_and_no_fee():
    acc = BankAccount("A", interest_rate=0.10)
    acc.deposit(100)
    result = acc.apply_monthly_statement()
    assert result["open_balance"] == pytest.approx(100.0)
    assert result["interest"] == pytest.approx(10.0)
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(110.0)


def test_statement_charges_fee_when_low_balance():
    acc = BankAccount("A", monthly_fee=2.5)
    acc.deposit(3)
    result = acc.apply_monthly_statement()
    assert result["fee"] == pytest.approx(2.5)
    assert result["close_balance"] == pytest.approx(0.5)


def test_statement_fee_waived_at_threshold():
    acc = BankAccount("A", monthly_fee=2.5)
    acc.deposit(5.0)  # exactly 2 * fee
    result = acc.apply_monthly_statement()
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(5.0)


def test_statement_zero_fee_config():
    acc = BankAccount("A", monthly_fee=0.0)
    acc.deposit(1)
    result = acc.apply_monthly_statement()
    assert result["fee"] == 0.0


def test_statement_fee_exceeds_overdraft():
    acc = BankAccount("A", overdraft_limit=1, monthly_fee=5)
    acc.deposit(1)
    with pytest.raises(ValueError):
        acc.apply_monthly_statement()


def test_statement_on_closed():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.apply_monthly_statement()


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------
def test_dispute_basic():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    # log: [deposit, withdraw]
    result = acc.dispute(1, 30)
    assert result == pytest.approx(100.0)
    log = acc.transactions()
    assert log[-1]["type"] == "refund"


def test_dispute_partial():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    result = acc.dispute(1, 10)
    assert result == pytest.approx(80.0)


def test_dispute_index_out_of_range_negative():
    acc = BankAccount("A")
    acc.deposit(100)
    with pytest.raises(ValueError):
        acc.dispute(-1, 10)


def test_dispute_index_out_of_range_high():
    acc = BankAccount("A")
    acc.deposit(100)
    with pytest.raises(ValueError):
        acc.dispute(5, 10)


def test_dispute_non_debit():
    acc = BankAccount("A")
    acc.deposit(100)
    with pytest.raises(ValueError):
        acc.dispute(0, 10)


def test_dispute_zero_amount():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    with pytest.raises(ValueError):
        acc.dispute(1, 0)


def test_dispute_exceeds_original():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    with pytest.raises(ValueError):
        acc.dispute(1, 31)


def test_dispute_twice():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    acc.dispute(1, 10)
    with pytest.raises(ValueError):
        acc.dispute(1, 10)


def test_dispute_on_closed():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    acc.close()
    with pytest.raises(ValueError):
        acc.dispute(1, 10)


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------
def test_history_all():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    history = acc.transaction_history()
    assert len(history) == 2


def test_history_filtered():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    deposits = acc.transaction_history("deposit")
    assert len(deposits) == 1
    assert deposits[0]["type"] == "deposit"


def test_history_unknown_kind():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.transaction_history("bogus")


def test_history_returns_copy():
    acc = BankAccount("A")
    acc.deposit(100)
    history = acc.transaction_history()
    history[0]["amount"] = 999
    assert acc.transactions()[0]["amount"] == 100.0


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------
def test_close_zero_balance():
    acc = BankAccount("A")
    acc.close()
    assert acc.closed is True
    log = acc.transactions()
    assert log[-1]["type"] == "close"


def test_close_nonzero_balance():
    acc = BankAccount("A")
    acc.deposit(10)
    with pytest.raises(ValueError):
        acc.close()


def test_close_twice():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.close()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def test_summary():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(30)
    acc.dispute(1, 10)
    summary = acc.summary()
    assert summary["owner"] == "A"
    assert summary["balance"] == pytest.approx(80.0)
    assert summary["overdraft_limit"] == 100.0
    assert summary["closed"] is False
    assert summary["transactions"] == len(acc.transactions())
    assert summary["disputes"] == 1


def test_summary_closed():
    acc = BankAccount("A")
    acc.close()
    summary = acc.summary()
    assert summary["closed"] is True
