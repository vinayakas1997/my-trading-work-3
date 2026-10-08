"""The cooldown and the symbol lockout see the scheduler's own losing trades, and only this stack's own money."""
from __future__ import annotations

import pytest

from vinu_live.book.positions import apply_fill, init_book
from vinu_live.trade_plan import guards
from vinu_live.trade_plan.orchestrator import cooldown_active


@pytest.fixture
def book(tmp_path):
    b = init_book(str(tmp_path / "book.db"))
    yield b
    b.close()


def _lose(book, symbol, n):
    for _ in range(n):
        apply_fill(book, symbol, "buy", 1.0, 10.0)
        apply_fill(book, symbol, "sell", 1.0, 9.0)


def test_three_losing_scheduler_trades_lock_the_symbol(book):
    _lose(book, "AAA", 3)
    locked, reason = guards.symbol_lockout_active(book, "AAA", losses=3, hours=72)
    assert locked and "lockout" in reason
    assert not guards.symbol_lockout_active(book, "BBB", losses=3, hours=72)[0]


def test_a_win_ends_the_streak(book):
    _lose(book, "AAA", 2)
    apply_fill(book, "AAA", "buy", 1.0, 10.0)
    apply_fill(book, "AAA", "sell", 1.0, 12.0)
    assert not guards.symbol_lockout_active(book, "AAA", losses=3, hours=72)[0]


def test_two_losses_in_a_row_start_the_cooldown(book, monkeypatch):
    monkeypatch.setattr("vinu_live.trade_plan.orchestrator.COOLDOWN_LOSSES", 2)
    monkeypatch.setattr("vinu_live.trade_plan.orchestrator.COOLDOWN_HOURS", 24.0)
    _lose(book, "AAA", 2)
    assert cooldown_active(book)[0]


def test_losses_made_with_the_other_money_do_not_lock_this_stack(book, monkeypatch):
    monkeypatch.setattr("vinu_live.trade_plan.orchestrator.COOLDOWN_LOSSES", 2)
    monkeypatch.setattr("vinu_live.trade_plan.orchestrator.COOLDOWN_HOURS", 24.0)
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    _lose(book, "AAA", 2)
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    assert not cooldown_active(book)[0]
    assert not guards.symbol_lockout_active(book, "AAA", losses=2, hours=72)[0]
