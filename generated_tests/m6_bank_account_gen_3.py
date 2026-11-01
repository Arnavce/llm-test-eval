"""LLM-generated pytest suite for benchmark.m6_bank_account (run 3, profile low).

Shallow suite: few scenarios and most assertions removed.
"""

from __future__ import annotations

import pytest

from benchmark.m6_bank_account import BankAccount, MIN_DEPOSIT, OVERDRAFT_FEE


def test_transfer_and_log() -> None:
    alice = BankAccount("Alice")
    bob = BankAccount("Bob")
    alice.deposit(100.0)
    alice.transfer(bob, 40.0)
    assert alice.balance == 60.0
    assert bob.balance == 40.0
    assert len(alice.transactions()) == 2


def test_rejected_operations() -> None:
    account = BankAccount("Ada", overdraft_limit=30.0)
    account.deposit(10.0)
    with pytest.raises(ValueError):
        account.withdraw(45.0)
    with pytest.raises(ValueError):
        account.deposit(0.5)
