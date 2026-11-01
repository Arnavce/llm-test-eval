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
    acct = BankAccount("X", overdraft_limit=0, monthly_fee=0, interest_rate=0)
    assert acct.overdraft_limit == 0.0
    assert acct.monthly_fee == 0.0


# ---------------------------------------------------------------------------
# Deposit
# ---------------------------------------------------------------------------
def test_deposit_basic():
    acct = BankAccount("A")
    assert acct.deposit(50) == 50.0
    assert acct.balance == 50.0


def test_deposit_minimum():
    acct = BankAccount("A")
    assert acct.deposit(MIN_DEPOSIT) == MIN_DEPOSIT


def test_deposit_below_minimum():
    acct = BankAccount("A")
    with pytest.raises(ValueError):
        acct.deposit(MIN_DEPOSIT - 0.01)


def test_deposit_zero():
    acct = BankAccount("A")
    with pytest.raises(ValueError):
        acct.deposit(0)


def test_deposit_negative():
    acct = BankAccount("A")
    with pytest.raises(ValueError):
        acct.deposit(-5)


def test_deposit_records_transaction():
    acct = BankAccount("A")
    acct.deposit(20)
    log = acct.transactions()
    assert len(log) == 1
    assert log[0]["type"] == "deposit"
    assert log[0]["amount"] == 20.0
    assert log[0]["balance"] == 20.0


def test_deposit_rounds_balance():
    acct = BankAccount("A")
    acct.deposit(10.005)
    assert acct.balance == pytest.approx(10.01, abs=1e-9)


# ---------------------------------------------------------------------------
# Withdraw
# ---------------------------------------------------------------------------
def test_withdraw_basic():
    acct = BankAccount("A")
    acct.deposit(100)
    assert acct.withdraw(40) == 60.0


def test_withdraw_zero():
    acct = BankAccount("A")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.withdraw(0)


def test_withdraw_negative():
    acct = BankAccount("A")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.withdraw(-1)


def test_withdraw_at_fee_free_limit_no_fee():
    acct = BankAccount("A")
    acct.deposit(200)
    acct.withdraw(BankAccount.FEE_FREE_LIMIT)
    assert acct.balance == pytest.approx(100.0)


def test_withdraw_above_fee_free_limit_charges_fee():
    acct = BankAccount("A", monthly_fee=2.5)
    acct.deposit(200)
    acct.withdraw(150)
    assert acct.balance == pytest.approx(200 - 150 - 2.5)


def test_withdraw_fee_recorded():
    acct = BankAccount("A", monthly_fee=2.5)
    acct.deposit(200)
    acct.withdraw(150)
    kinds = [t["type"] for t in acct.transactions()]
    assert kinds == ["deposit", "withdraw"]


def test_withdraw_exceeds_overdraft():
    acct = BankAccount("A", overdraft_limit=100)
    acct.deposit(50)
    with pytest.raises(ValueError):
        acct.withdraw(151)


def test_withdraw_exact_overdraft_limit():
    acct = BankAccount("A", overdraft_limit=100)
    acct.deposit(50)
    # projected = 50 - 150 = -100, allowed, but overdraft fee applies
    with pytest.raises(ValueError):
        acct.withdraw(150)


def test_withdraw_partial_overdraft_incurs_fee():
    acct = BankAccount("A", overdraft_limit=100)
    acct.deposit(50)
    result = acct.withdraw(60)
    # projected = -10, then overdraft fee 10 -> -20
    assert result == pytest.approx(-20.0)
    kinds = [t["type"] for t in acct.transactions()]
    assert kinds == ["deposit", "withdraw", "fee"]


def test_withdraw_overdraft_fee_not_covered():
    acct = BankAccount("A", overdraft_limit=100)
    acct.deposit(50)
    # projected = 50 - 145 = -95, fee -> -105 < -100
    with pytest.raises(ValueError):
        acct.withdraw(145)


def test_withdraw_zero_overdraft_limit():
    acct = BankAccount("A", overdraft_limit=0)
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.withdraw(101)


def test_withdraw_zero_overdraft_limit_exact():
    acct = BankAccount("A", overdraft_limit=0)
    acct.deposit(100)
    assert acct.withdraw(100) == 0.0


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


def test_transfer_invalid_target():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer("not an account", 10)  # type: ignore[arg-type]


def test_transfer_to_self():
    a = BankAccount("A")
    a.deposit(100)
    with pytest.raises(ValueError):
        a.transfer(a, 10)


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


def test_transfer_insufficient_funds():
    a = BankAccount("A", overdraft_limit=0)
    b = BankAccount("B")
    a.deposit(10)
    with pytest.raises(ValueError):
        a.transfer(b, 20)


# ---------------------------------------------------------------------------
# Interest
# ---------------------------------------------------------------------------
def test_interest_positive_balance():
    acct = BankAccount("A", interest_rate=0.01)
    acct.deposit(1000)
    result = acct.apply_monthly_interest()
    assert result == pytest.approx(1010.0)


def test_interest_zero_rate():
    acct = BankAccount("A", interest_rate=0.0)
    acct.deposit(1000)
    assert acct.apply_monthly_interest() == 1000.0
    assert len(acct.transactions()) == 1


def test_interest_zero_balance():
    acct = BankAccount("A", interest_rate=0.05)
    assert acct.apply_monthly_interest() == 0.0
    assert acct.transactions() == []


def test_interest_negative_balance():
    acct = BankAccount("A", interest_rate=0.05, overdraft_limit=100)
    acct.deposit(10)
    acct.withdraw(20)
    before = acct.balance
    assert acct.apply_monthly_interest() == before


def test_interest_closed_account():
    acct = BankAccount("A", interest_rate=0.05)
    acct.close()
    with pytest.raises(ValueError):
        acct.apply_monthly_interest()


def test_interest_records_transaction():
    acct = BankAccount("A", interest_rate=0.01)
    acct.deposit(1000)
    acct.apply_monthly_interest()
    log = acct.transactions()
    assert log[-1]["type"] == "interest"
    assert log[-1]["amount"] == pytest.approx(10.0)


# ---------------------------------------------------------------------------
# Statement
# ---------------------------------------------------------------------------
def test_statement_basic():
    acct = BankAccount("A", interest_rate=0.01, monthly_fee=2.5)
    acct.deposit(1000)
    result = acct.apply_monthly_statement()
    assert result["open_balance"] == 1000.0
    assert result["interest"] == pytest.approx(10.0)
    assert result["fee"] == 0.0
    assert result["close_balance"] == pytest.approx(1010.0)


def test_statement_charges_fee_when_low_balance():
    acct = BankAccount("A", interest_rate=0.0, monthly_fee=2.5)
    acct.deposit(3)
    result = acct.apply_monthly_statement()
    assert result["fee"] == 2.5
    assert result["close_balance"] == pytest.approx(0.5)


def test_statement_fee_waived_at_threshold():
    acct = BankAccount("A", interest_rate=0.0, monthly_fee=2.5)
    acct.deposit(5.0)
    result = acct.apply_monthly_statement()
    assert result["fee"] == 0.0
    assert result["close_balance"] == 5.0


def test_statement_fee_exceeds_overdraft():
    acct = BankAccount("A", interest_rate=0.0, monthly_fee=2.5, overdraft_limit=1)
    acct.deposit(1)
    with pytest.raises(ValueError):
        acct.apply_monthly_statement()


def test_statement_zero_fee():
    acct = BankAccount("A", interest_rate=0.0, monthly_fee=0.0)
    acct.deposit(1)
    result = acct.apply_monthly_statement()
    assert result["fee"] == 0.0


def test_statement_closed():
    acct = BankAccount("A")
    acct.close()
    with pytest.raises(ValueError):
        acct.apply_monthly_statement()


def test_statement_negative_balance_no_interest():
    acct = BankAccount("A", interest_rate=0.05, monthly_fee=0.0, overdraft_limit=100)
    acct.deposit(10)
    acct.withdraw(20)
    result = acct.apply_monthly_statement()
    assert result["interest"] == 0.0


# ---------------------------------------------------------------------------
# Dispute
# ---------------------------------------------------------------------------
def test_dispute_basic():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    result = acct.dispute(1, 30)
    assert result == pytest.approx(100.0)


def test_dispute_partial():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    result = acct.dispute(1, 10)
    assert result == pytest.approx(80.0)


def test_dispute_index_out_of_range_negative():
    acct = BankAccount("A")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.dispute(-1, 10)


def test_dispute_index_out_of_range_high():
    acct = BankAccount("A")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.dispute(5, 10)


def test_dispute_non_debit():
    acct = BankAccount("A")
    acct.deposit(100)
    with pytest.raises(ValueError):
        acct.dispute(0, 10)


def test_dispute_zero_amount():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    with pytest.raises(ValueError):
        acct.dispute(1, 0)


def test_dispute_negative_amount():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    with pytest.raises(ValueError):
        acct.dispute(1, -5)


def test_dispute_exceeds_original():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    with pytest.raises(ValueError):
        acct.dispute(1, 31)


def test_dispute_exact_original():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    assert acct.dispute(1, 30) == pytest.approx(100.0)


def test_dispute_twice():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    acct.dispute(1, 30)
    with pytest.raises(ValueError):
        acct.dispute(1, 30)


def test_dispute_fee_transaction():
    acct = BankAccount("A", overdraft_limit=100)
    acct.deposit(50)
    acct.withdraw(60)  # creates withdraw + fee
    # fee entry is index 2
    result = acct.dispute(2, 10)
    assert result == pytest.approx(-10.0)


def test_dispute_closed():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    acct.close()
    with pytest.raises(ValueError):
        acct.dispute(1, 10)


def test_dispute_records_refund():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    acct.dispute(1, 30)
    log = acct.transactions()
    assert log[-1]["type"] == "refund"
    assert log[-1]["amount"] == 30.0


# ---------------------------------------------------------------------------
# transaction_history
# ---------------------------------------------------------------------------
def test_history_all():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    history = acct.transaction_history()
    assert len(history) == 2


def test_history_filter():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    history = acct.transaction_history("deposit")
    assert len(history) == 1
    assert history[0]["type"] == "deposit"


def test_history_filter_no_match():
    acct = BankAccount("A")
    acct.deposit(100)
    assert acct.transaction_history("withdraw") == []


def test_history_unknown_kind():
    acct = BankAccount("A")
    with pytest.raises(ValueError):
        acct.transaction_history("bogus")


def test_history_returns_copy():
    acct = BankAccount("A")
    acct.deposit(100)
    history = acct.transaction_history()
    history[0]["amount"] = 999
    assert acct.transactions()[0]["amount"] == 100.0


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------
def test_close_zero_balance():
    acct = BankAccount("A")
    acct.close()
    assert acct.closed is True


def test_close_nonzero_balance():
    acct = BankAccount("A")
    acct.deposit(10)
    with pytest.raises(ValueError):
        acct.close()


def test_close_twice():
    acct = BankAccount("A")
    acct.close()
    with pytest.raises(ValueError):
        acct.close()


def test_close_records_transaction():
    acct = BankAccount("A")
    acct.close()
    log = acct.transactions()
    assert log[-1]["type"] == "close"


def test_operations_after_close():
    acct = BankAccount("A")
    acct.close()
    with pytest.raises(ValueError):
        acct.deposit(10)
    with pytest.raises(ValueError):
        acct.withdraw(10)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def test_summary():
    acct = BankAccount("A", overdraft_limit=50)
    acct.deposit(100)
    acct.withdraw(30)
    summary = acct.summary()
    assert summary["owner"] == "A"
    assert summary["balance"] == pytest.approx(70.0)
    assert summary["overdraft_limit"] == 50.0
    assert summary["closed"] is False
    assert summary["transactions"] == 2
    assert summary["disputes"] == 0


def test_summary_after_dispute():
    acct = BankAccount("A")
    acct.deposit(100)
    acct.withdraw(30)
    acct.dispute(1, 30)
    summary = acct.summary()
    assert summary["disputes"] == 1


# ---------------------------------------------------------------------------
# Balance rounding
# ---------------------------------------------------------------------------
def test_balance_rounding():
    acct = BankAccount("A")
    acct.deposit(0.1)
    acct.deposit(0.2)
    assert acct.balance == pytest.approx(0.3, abs=1e-9)
