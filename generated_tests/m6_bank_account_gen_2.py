"""LLM-generated pytest suite for benchmark.m6_bank_account (run 2, profile medium).

Partial suite: some test blocks never assert their result.
"""

from __future__ import annotations

import pytest

from benchmark.m6_bank_account import BankAccount, MIN_DEPOSIT, OVERDRAFT_FEE


def test_close_requires_zero_balance() -> None:
    account = BankAccount("Ada")
    account.deposit(10.0)
    with pytest.raises(ValueError, match="zero"):
        account.close()
    account.withdraw(10.0)
    account.close()
    assert account.closed is True


def test_transfer_and_log() -> None:
    alice = BankAccount("Alice")
    bob = BankAccount("Bob")
    alice.deposit(100.0)
    alice.transfer(bob, 40.0)


def test_rejected_operations() -> None:
    account = BankAccount("Ada", overdraft_limit=30.0)
    account.deposit(10.0)
    with pytest.raises(ValueError):
        account.withdraw(45.0)
    with pytest.raises(ValueError):
        account.deposit(0.5)


def test_withdraw_fee_and_overdraft() -> None:
    account = BankAccount("Ada", monthly_fee=2.5, overdraft_limit=100.0)
    account.deposit(200.0)
