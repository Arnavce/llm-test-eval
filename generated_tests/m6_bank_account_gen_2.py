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
    acc = BankAccount("Carol", overdraft_limit=50, monthly_fee=1.0, interest_rate=0.05)
    assert acc.overdraft_limit == 50.0
    assert acc.monthly_fee == 1.0
    assert acc.interest_rate == 0.05


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
    assert acc.deposit(10) == 10.0
    assert acc.balance == 10.0


def test_deposit_minimum():
    acc = BankAccount("A")
    assert acc.deposit(MIN_DEPOSIT) == MIN_DEPOSIT


def test_deposit_below_minimum():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.deposit(MIN_DEPOSIT - 0.01)


def test_deposit_zero():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.deposit(0)


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
    acc.deposit(1.005)
    assert acc.balance == pytest.approx(1.0, abs=0.01)


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
    assert acc.withdraw(30) == 70.0


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


def test_withdraw_on_closed_account():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.withdraw(1)


def test_withdraw_fee_free_limit_exact():
    acc = BankAccount("A")
    acc.deposit(200)
    # amount == FEE_FREE_LIMIT -> no fee
    assert acc.withdraw(BankAccount.FEE_FREE_LIMIT) == 100.0


def test_withdraw_above_fee_free_limit_charges_fee():
    acc = BankAccount("A")
    acc.deposit(200)
    result = acc.withdraw(150)
    assert result == pytest.approx(200 - 150 - BankAccount.MONTHLY_FEE)


def test_withdraw_insufficient_funds():
    acc = BankAccount("A")
    acc.deposit(10)
    with pytest.raises(ValueError):
        acc.withdraw(200)


def test_withdraw_partial_overdraft_incurs_fee():
    acc = BankAccount("A", overdraft_limit=100)
    acc.deposit(10)
    result = acc.withdraw(50)
    # projected = 10 - 50 = -40, overdraft fee 10 -> -50
    assert result == pytest.approx(-50.0)
    log = acc.transactions()
    assert any(e["type"] == "fee" and e["amount"] == OVERDRAFT_FEE for e in log)


def test_withdraw_overdraft_fee_not_covered():
    acc = BankAccount("A", overdraft_limit=5)
    acc.deposit(10)
    # projected = 10 - 14 = -4, fee -> -14 < -5 -> error
    with pytest.raises(ValueError):
        acc.withdraw(14)


def test_withdraw_exact_overdraft_limit():
    acc = BankAccount("A", overdraft_limit=100)
    acc.deposit(100)
    # projected = 100 - 200 = -100, fee -> -110 < -100 -> error
    with pytest.raises(ValueError):
        acc.withdraw(200)


def test_withdraw_records_transaction():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    log = acc.transactions()
    assert log[-1]["type"] == "withdraw"
    assert log[-1]["amount"] == 20.0


# ---------------------------------------------------------------------------
# Transfer
# ---------------------------------------------------------------------------
def test_transfer_basic():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    result = a.transfer(b, 40)
    assert result == 60.0
    assert b.balance == 40.0


def test_transfer_to_non_account():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer("not an account", 10)  # type: ignore[arg-type]


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


def test_transfer_zero():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(b, 0)


def test_transfer_negative():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(b, -5)


def test_transfer_insufficient():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(10)
    with pytest.raises(ValueError):
        a.transfer(b, 500)


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------
def test_interest_zero_balance():
    acc = BankAccount("A", interest_rate=0.1)
    assert acc.apply_monthly_interest() == 0.0
    assert acc.transactions() == []


def test_interest_zero_rate():
    acc = BankAccount("A", interest_rate=0.0)
    acc.deposit(100)
    assert acc.apply_monthly_interest() == 100.0
    assert len(acc.transactions()) == 1


def test_interest_positive():
    acc = BankAccount("A", interest_rate=0.1)
    acc.deposit(100)
    assert acc.apply_monthly_interest() == pytest.approx(110.0)
    log = acc.transactions()
    assert log[-1]["type"] == "interest"
    assert log[-1]["amount"] == pytest.approx(10.0)


def test_interest_negative_balance():
    acc = BankAccount("A", interest_rate=0.1, overdraft_limit=100)
    acc.deposit(10)
    acc.withdraw(50)
    before = acc.balance
    assert acc.apply_monthly_interest() == before


def test_interest_on_closed():
    acc = BankAccount("A", interest_rate=0.1)
    acc.close()
    with pytest.raises(ValueError):
        acc.apply_monthly_interest()


# ---------------------------------------------------------------------------
# Statement
# ---------------------------------------------------------------------------
def test_statement_basic():
    acc = BankAccount("A", interest_rate=0.1)
    acc.deposit(100)
    result = acc.apply_monthly_statement()
    assert result["open_balance"] == 100.0
    assert result["interest"] == pytest.approx(10.0)
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(110.0)


def test_statement_fee_charged_low_balance():
    acc = BankAccount("A", monthly_fee=2.5)
    acc.deposit(3)
    result = acc.apply_monthly_statement()
    assert result["fee"] == 2.5
    assert result["close_balance"] == pytest.approx(0.5)


def test_statement_fee_waived_at_threshold():
    acc = BankAccount("A", monthly_fee=2.5)
    acc.deposit(5.0)  # exactly 2 * fee
    result = acc.apply_monthly_statement()
    assert result["fee"] == 0.0
    assert result["close_balance"] == 5.0


def test_statement_zero_fee():
    acc = BankAccount("A", monthly_fee=0.0)
    acc.deposit(1)
    result = acc.apply_monthly_statement()
    assert result["fee"] == 0.0


def test_statement_fee_exceeds_overdraft():
    acc = BankAccount("A", monthly_fee=10.0, overdraft_limit=1.0)
    acc.deposit(1.0)
    with pytest.raises(ValueError):
        acc.apply_monthly_statement()


def test_statement_on_closed():
    acc = BankAccount("A")
    acc.close()
    with pytest.raises(ValueError):
        acc.apply_monthly_statement()


def test_statement_no_interest_negative_balance():
    acc = BankAccount("A", interest_rate=0.1, overdraft_limit=100)
    acc.deposit(10)
    acc.withdraw(50)
    result = acc.apply_monthly_statement()
    assert result["interest"] == 0.0


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------
def test_dispute_basic():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    # index 1 is the withdraw
    result = acc.dispute(1, 20)
    assert result == pytest.approx(100.0)
    log = acc.transactions()
    assert log[-1]["type"] == "refund"


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
    acc.withdraw(20)
    with pytest.raises(ValueError):
        acc.dispute(1, 0)


def test_dispute_exceeds_original():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    with pytest.raises(ValueError):
        acc.dispute(1, 25)


def test_dispute_already_disputed():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    acc.dispute(1, 10)
    with pytest.raises(ValueError):
        acc.dispute(1, 10)


def test_dispute_on_closed():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    acc.close()
    with pytest.raises(ValueError):
        acc.dispute(1, 10)


def test_dispute_fee_transaction():
    acc = BankAccount("A", overdraft_limit=100)
    acc.deposit(10)
    acc.withdraw(50)
    # log: deposit(0), withdraw(1), fee(2)
    result = acc.dispute(2, 10)
    assert result == pytest.approx(-40.0)


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------
def test_history_all():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    hist = acc.transaction_history()
    assert len(hist) == 2


def test_history_filtered():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    hist = acc.transaction_history("deposit")
    assert len(hist) == 1
    assert hist[0]["type"] == "deposit"


def test_history_unknown_kind():
    acc = BankAccount("A")
    with pytest.raises(ValueError):
        acc.transaction_history("bogus")


def test_history_returns_copy():
    acc = BankAccount("A")
    acc.deposit(100)
    hist = acc.transaction_history()
    hist[0]["amount"] = 999
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
    acc = BankAccount("A", overdraft_limit=50)
    acc.deposit(100)
    acc.withdraw(20)
    s = acc.summary()
    assert s["owner"] == "A"
    assert s["balance"] == 80.0
    assert s["overdraft_limit"] == 50.0
    assert s["closed"] is False
    assert s["transactions"] == 2
    assert s["disputes"] == 0


def test_summary_after_dispute_and_close():
    acc = BankAccount("A")
    acc.deposit(100)
    acc.withdraw(20)
    acc.dispute(1, 20)
    acc.withdraw(100)
    acc.close()
    s = acc.summary()
    assert s["closed"] is True
    assert s["disputes"] == 1
