"""Real-money base: the order guard refuses an entry larger than the free cash, and refuses when the ledger is unreadable or
belongs to the other money mode. Exits are never held back."""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.broker.guard_codes import ReasonCode
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard
from vinu_infra.sessions import NY


def _guard() -> OrderGuard:
    broker = MagicMock()
    broker.get_clock.return_value = {"is_open": True, "timestamp": datetime(2026, 10, 5, 11, tzinfo=NY).isoformat(), "next_open": "x"}
    broker.get_account.return_value = MagicMock(equity=100_000.0, cash=100_000.0, portfolio_value=100_000.0, buying_power=100_000.0)
    mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=False)
    return OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"), portfolio_api_url="http://127.0.0.1:9")


@pytest.fixture(autouse=True)
def isolated(monkeypatch):
    from vinu_agent.broker.symbol_limits import SymbolLimitStore, reset_limit_store
    from vinu_agent.broker.symbol_overrides import SymbolOverrideStore, reset_override_store

    reset_override_store(SymbolOverrideStore(":memory:"))
    reset_limit_store(SymbolLimitStore(":memory:"))
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    yield
    reset_override_store(None)
    reset_limit_store(None)


LEDGER = {"status": "ok", "account_mode": "real", "capped": True, "free_cash": 10.24, "real_capital": 20.0,
          "committed": 1.76, "reserve": 8.0}


def _check(g, ledger, side="buy", qty=1, price=5.0, **kw):
    with patch("vinu_agent.broker.order_guard.fetch_capital_ledger", return_value=ledger):
        return g.check("AAA", side, qty=qty, price=price, order_type="limit", **kw)


def test_an_entry_within_the_free_cash_passes():
    assert _check(_guard(), LEDGER, qty=2, price=5.0)          # 10.00 <= 10.24


def test_an_entry_above_the_free_cash_is_refused_with_the_figures():
    r = _check(_guard(), LEDGER, qty=3, price=5.0)             # 15.00 > 10.24
    assert not r and r.code == ReasonCode.EXCEEDS_FREE_CASH and "10.24" in r.reason and "reserve" in r.reason


def test_an_unreadable_ledger_refuses_entries():
    r = _check(_guard(), None)
    assert not r and r.code == ReasonCode.CAPITAL_LEDGER_UNAVAILABLE


def test_a_ledger_of_the_other_money_mode_refuses_entries():
    r = _check(_guard(), {**LEDGER, "account_mode": "paper"})
    assert not r and r.code == ReasonCode.ACCOUNT_MODE_MISMATCH


def test_an_exit_is_never_held_back_by_the_free_cash_check():
    assert _check(_guard(), None, side="sell", qty=3, price=5.0, reduce_only=True)


def test_without_a_capital_base_the_check_does_nothing(monkeypatch):
    monkeypatch.delenv("VINU_REAL_CAPITAL", raising=False)
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "paper")
    assert _check(_guard(), None, qty=3, price=5.0)
