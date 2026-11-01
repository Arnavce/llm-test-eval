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
    acct = BankAccount("Alice")
    assert acct.owner == "Alice"
    assert acct.overdraft_limit == 100.0
    assert acct.monthly_fee == BankAccount.MONTHLY_FEE
    assert acct.interest_rate == 0.0
    assert acct.balance == 0.0
    assert acct.closed is False
    assert acct.transactions() == []


def test_constructor_strips_owner():
    acct = BankAccount("  Bob  ")
    assert acct.owner == "Bob"


def test_constructor_custom_values():
    acct = BankAccount("Carol", overdraft_limit=50, monthly_fee=1.5, interest_rate=0.02)
    assert acct.overdraft_limit == 50.0
    assert acct.monthly_fee == 1.5
    assert acct.interest_rate == 0.02


@pytest.mark.parametrize("owner", ["", "   ", None, 123])
def test_constructor_blank_owner(owner):
    with pytest.raises(ValueError):
        BankAccount(owner)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"overdraft_limit": -1},
        {"monthly_fee": -0.01},
        {"interest_rate": -0.001},
    ],
)
def test_constructor_negative_args(kwargs):
    with pytest.raises(ValueError):
        BankAccount("Dave", **kwargs)


def test_constructor_zero_limits_allowed():
    acct = BankAccount("Eve", overdraft_limit=0, monthly_fee=0, interest_rate=0)
    assert acct.overdraft_limit == 0.0
    assert acct.monthly_fee == 0.0
    assert acct.interest_rate == 0.0


# ---------------------------------------------------------------------------
# Deposit
# ---------------------------------------------------------------------------
def test_deposit_returns_balance():
    acct = BankAccount("Alice")
    assert acct.deposit(50) == 50.0
    assert acct.balance == 50.0


def test_deposit_minimum():
    acct = BankAccount("Alice")
    assert acct.deposit(MIN_DEPOSIT) == MIN_DEPOSIT


def test_deposit_below_minimum():
    acct = BankAccount("Alice")
    with pytest.raises(ValueError):
        acct.deposit(MIN_DEPOSIT - 0.01)
    assert acct.balance == 0.0


def test_deposit_logs_transaction():
    acct = BankAccount("Alice")
    acct.deposit(25.5)
    log = acct.transactions()
    assert len(log) == 1
    assert log[0]["type"] == "deposit"
    assert log[0]["amount"] == pytest.approx(25.5)
    assert log[0]["balance"] == pytest.approx(25.5)


def test_deposit_rounds_balance():
    acct = BankAccount("Alice")
    acct.deposit(10.005)
    assert acct.balance == pytest.approx(10.01)


def test_deposit_on_closed_account():
    acct = BankAccount("Alice")
    acct.close()
    with pytest.raises(ValueError):
        acct.deposit(10)


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------
def test_withdraw_basic():
    acct = BankAccount("Alice")
    acct.deposit(100)
    assert acct.withdraw(40) == 60.0


def test_withdraw_zero_or_negative():
    acct = BankAccount("Alice")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.withdraw(0)
    with pytest.raises(ValueError):
        acct.withdraw(-5)


def test_withdraw_fee_free_limit_boundary():
    acct = BankAccount("Alice")
    acct.deposit(500)
    # exactly at limit -> no fee
    assert acct.withdraw(BankAccount.FEE_FREE_LIMIT) == pytest.approx(400.0)


def test_withdraw_above_limit_charges_fee():
    acct = BankAccount("Alice")
    acct.deposit(500)
    result = acct.withdraw(150)
    assert result == pytest.approx(500 - 150 - BankAccount.MONTHLY_FEE)


def test_withdraw_overdraft_fee_applied():
    acct = BankAccount("Alice")
    acct.deposit(50)
    result = acct.withdraw(60)
    # projected = 50 - 60 = -10 -> overdraft fee 10 -> -20
    assert result == pytest.approx(-20.0)
    log = acct.transactions()
    assert any(e["type"] == "fee" and e["amount"] == pytest.approx(OVERDRAFT_FEE) for e in log)


def test_withdraw_exceeds_overdraft_limit():
    acct = BankAccount("Alice", overdraft_limit=10)
    acct.deposit(5)
    with pytest.raises(ValueError):
        acct.withdraw(20)


def test_withdraw_overdraft_fee_not_covered():
    acct = BankAccount("Alice", overdraft_limit=15)
    acct.deposit(5)
    # projected = 5 - 15 = -10, fee -> -20 < -15 -> error
    with pytest.raises(ValueError):
        acct.withdraw(15)


def test_withdraw_exact_overdraft_limit():
    acct = BankAccount("Alice", overdraft_limit=10)
    acct.deposit(5)
    # projected = -5, fee -> -15 < -10 -> error
    with pytest.raises(ValueError):
        acct.withdraw(10)


def test_withdraw_on_closed_account():
    acct = BankAccount("Alice")
    acct.close()
    with pytest.raises(ValueError):
        acct.withdraw(1)


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


def test_transfer_invalid_target():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer("not-an-account", 10)


def test_transfer_to_self():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(a, 10)


def test_transfer_non_positive():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(b, 0)
    with pytest.raises(ValueError):
        a.transfer(b, -1)


def test_transfer_closed_source():
    a = BankAccount("A")
    b = BankAccount("B")
    a.close()
    with pytest.raises(ValueError):
        a.transfer(b, 10)


def test_transfer_closed_target():
    a = BankAccount("A")
    b = BankAccount("B")
    a.deposit(100)
    b.close()
    with pytest.raises(ValueError):
        a.transfer(b, 10)


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------
def test_interest_zero_rate():
    acct = BankAccount("Alice", interest_rate=0.0)
    acct.deposit(100)
    assert acct.apply_monthly_interest() == pytest.approx(100.0)
    assert len(acct.transactions()) == 1


def test_interest_positive_balance():
    acct = BankAccount("Alice", interest_rate=0.01)
    acct.deposit(1000)
    result = acct.apply_monthly_interest()
    assert result == pytest.approx(1010.0)
    log = acct.transactions()
    assert log[-1]["type"] == "interest"
    assert log[-1]["amount"] == pytest.approx(10.0)


def test_interest_zero_balance():
    acct = BankAccount("Alice", interest_rate=0.05)
    assert acct.apply_monthly_interest() == 0.0
    assert acct.transactions() == []


def test_interest_negative_balance():
    acct = BankAccount("Alice", interest_rate=0.05)
    acct.deposit(10)
    acct.withdraw(20)  # balance negative
    before = acct.balance
    assert acct.apply_monthly_interest() == before


def test_interest_closed_account():
    acct = BankAccount("Alice", interest_rate=0.05)
    acct.close()
    with pytest.raises(ValueError):
        acct.apply_monthly_interest()


# ---------------------------------------------------------------------------
# Monthly statement
# ---------------------------------------------------------------------------
def test_statement_interest_and_no_fee():
    acct = BankAccount("Alice", interest_rate=0.01, monthly_fee=2.5)
    acct.deposit(1000)
    result = acct.apply_monthly_statement()
    assert result["open_balance"] == pytest.approx(1000.0)
    assert result["interest"] == pytest.approx(10.0)
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(1010.0)


def test_statement_fee_charged():
    acct = BankAccount("Alice", interest_rate=0.0, monthly_fee=2.5)
    acct.deposit(3.0)
    result = acct.apply_monthly_statement()
    assert result["interest"] == 0.0
    assert result["fee"] == pytest.approx(2.5)
    assert result["close_balance"] == pytest.approx(0.5)


def test_statement_fee_waived_at_threshold():
    acct = BankAccount("Alice", interest_rate=0.0, monthly_fee=2.5)
    acct.deposit(5.0)  # exactly 2 * fee
    result = acct.apply_monthly_statement()
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(5.0)


def test_statement_zero_fee():
    acct = BankAccount("Alice", interest_rate=0.0, monthly_fee=0.0)
    acct.deposit(1.0)
    result = acct.apply_monthly_statement()
    assert result["fee"] == 0.0


def test_statement_fee_exceeds_overdraft():
    acct = BankAccount("Alice", overdraft_limit=1.0, monthly_fee=2.5, interest_rate=0.0)
    acct.deposit(1.0)
    acct.withdraw(1.0)  # balance 0
    with pytest.raises(ValueError):
        acct.apply_monthly_statement()


def test_statement_closed_account():
    acct = BankAccount("Alice")
    acct.close()
    with pytest.raises(ValueError):
        acct.apply_monthly_statement()


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------
def test_dispute_withdraw():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    # log: [deposit, withdraw]
    result = acct.dispute(1, 30)
    assert result == pytest.approx(100.0)


def test_dispute_partial():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    result = acct.dispute(1, 10)
    assert result == pytest.approx(80.0)


def test_dispute_index_out_of_range():
    acct = BankAccount("Alice")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.dispute(5, 10)
    with pytest.raises(ValueError):
        acct.dispute(-1, 10)


def test_dispute_non_debit():
    acct = BankAccount("Alice")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.dispute(0, 10)


def test_dispute_non_positive_amount():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    with pytest.raises(ValueError):
        acct.dispute(1, 0)
    with pytest.raises(ValueError):
        acct.dispute(1, -5)


def test_dispute_exceeds_original():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    with pytest.raises(ValueError):
        acct.dispute(1, 31)


def test_dispute_twice():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    acct.dispute(1, 10)
    with pytest.raises(ValueError):
        acct.dispute(1, 10)


def test_dispute_closed_account():
    acct = BankAccount("Alice")
    acct.close()
    with pytest.raises(ValueError):
        acct.dispute(0, 1)


def test_dispute_fee_transaction():
    acct = BankAccount("Alice")
    acct.deposit(50)
    acct.withdraw(60)  # creates withdraw + fee entries
    log = acct.transactions()
    fee_idx = next(i for i, e in enumerate(log) if e["type"] == "fee")
    result = acct.dispute(fee_idx, OVERDRAFT_FEE)
    assert result == pytest.approx(-10.0)


# ---------------------------------------------------------------------------
# Transaction history
# ---------------------------------------------------------------------------
def test_history_all():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(10)
    hist = acct.transaction_history()
    assert len(hist) == 2


def test_history_filtered():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(10)
    deposits = acct.transaction_history("deposit")
    assert len(deposits) == 1
    assert deposits[0]["type"] == "deposit"


def test_history_unknown_kind():
    acct = BankAccount("Alice")
    with pytest.raises(ValueError):
        acct.transaction_history("bogus")


def test_history_returns_copy():
    acct = BankAccount("Alice")
    acct.deposit(100)
    hist = acct.transactions()
    hist[0]["amount"] = 999
    assert acct.transactions()[0]["amount"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------
def test_close_zero_balance():
    acct = BankAccount("Alice")
    acct.close()
    assert acct.closed is True
    log = acct.transactions()
    assert log[-1]["type"] == "close"


def test_close_nonzero_balance():
    acct = BankAccount("Alice")
    acct.deposit(10)
    with pytest.raises(ValueError):
        acct.close()


def test_close_twice():
    acct = BankAccount("Alice")
    acct.close()
    with pytest.raises(ValueError):
        acct.close()


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def test_summary():
    acct = BankAccount("Alice", overdraft_limit=50, interest_rate=0.01)
    acct.deposit(100)
    acct.withdraw(10)
    s = acct.summary()
    assert s["owner"] == "Alice"
    assert s["balance"] == pytest.approx(90.0)
    assert s["overdraft_limit"] == 50.0
    assert s["closed"] is False
    assert s["transactions"] == 2
    assert s["disputes"] == 0


def test_summary_after_dispute_and_close():
    acct = BankAccount("Alice")
    acct.deposit(100)
    acct.withdraw(30)
    acct.dispute(1, 10)
    acct.withdraw(80)  # bring balance to 0
    acct.close()
    s = acct.summary()
    assert s["closed"] is True
    assert s["disputes"] == 1
