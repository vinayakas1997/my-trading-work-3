"""Per-symbol loss lockout (v1 C1 / the v2 gap list): the portfolio-wide cooldown locks ALL entries after N losses in
a row; this locks only the NAME that keeps losing. Opt-in (VINU_LIVE_SYMBOL_LOCKOUT_LOSSES, default 0 = off);
entries only, never an exit; a win or flat trade on the symbol resets its streak; every lock has a reason and an expiry.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import vinu_live.trade_plan.guards as guards
from vinu_live.book.positions import close_position, init_book, open_position
from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan  # noqa: F401  (import check: package intact)
from vinu_live.scheduler import LiveScheduler
from vinu_live.server.app import create_app
from vinu_live.signal_translator import OrderInstruction
from vinu_live.trade_plan.guards import active_symbol_lockouts, symbol_lockout, symbol_lockout_active

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def _row(hours_ago, pnl):
    return {"realized_pnl": pnl, "closed_at": (NOW - timedelta(hours=hours_ago)).isoformat()}


# ------------------------------------------------------------------ the pure rule

def test_disabled_values_never_lock():
    rows = [_row(1, -5), _row(2, -5), _row(3, -5)]
    assert symbol_lockout(rows, losses=0, hours=72, now=NOW) is None
    assert symbol_lockout(rows, losses=2, hours=0, now=NOW) is None


def test_two_losses_in_a_row_lock_with_a_streak_loss_total_and_expiry():
    lock = symbol_lockout([_row(30, 10), _row(5, -20), _row(2, -30)], losses=2, hours=72, now=NOW)
    assert lock["streak"] == 2 and lock["total_loss"] == -50.0
    assert lock["last_loss_at"] == (NOW - timedelta(hours=2)).isoformat()
    assert lock["locked_until"] == (NOW - timedelta(hours=2) + timedelta(hours=72)).isoformat()
    assert "all lost" in lock["reason"] and "entries locked until" in lock["reason"]


def test_fewer_than_n_losses_do_not_lock():
    assert symbol_lockout([_row(2, -30)], losses=2, hours=72, now=NOW) is None
    assert symbol_lockout([_row(5, 8), _row(2, -30)], losses=2, hours=72, now=NOW) is None


@pytest.mark.parametrize("breaker_pnl", [0.0, 12.0])
def test_a_win_or_flat_trade_resets_the_streak(breaker_pnl):
    rows = [_row(9, -10), _row(8, -10), _row(3, breaker_pnl), _row(1, -10)]
    assert symbol_lockout(rows, losses=2, hours=72, now=NOW) is None          # only one loss since the reset


def test_the_lock_expires_hours_after_the_latest_loss():
    rows = [_row(80, -10), _row(75, -10)]                                     # latest loss 75h ago, 72h lock
    assert symbol_lockout(rows, losses=2, hours=72, now=NOW) is None
    assert symbol_lockout(rows, losses=2, hours=100, now=NOW) is not None


def test_row_order_does_not_matter():
    a = [_row(5, -20), _row(2, -30), _row(30, 10)]
    b = list(reversed(a))
    assert symbol_lockout(a, losses=2, hours=72, now=NOW) == symbol_lockout(b, losses=2, hours=72, now=NOW)


def test_rows_without_a_usable_timestamp_cannot_start_a_lock():
    rows = [{"realized_pnl": -5, "closed_at": "garbage"}, {"realized_pnl": -5, "closed_at": None}, {"realized_pnl": -5}]
    assert symbol_lockout(rows, losses=2, hours=72, now=NOW) is None


def test_naive_timestamps_are_read_as_utc():
    naive = (NOW - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    rows = [{"realized_pnl": -1, "closed_at": naive}, {"realized_pnl": -1, "closed_at": naive}]
    assert symbol_lockout(rows, losses=2, hours=72, now=NOW) is not None


# ------------------------------------------------------------------ against a real book

@pytest.fixture
def book():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    be = init_book(path)
    yield be
    be.close()
    if os.path.exists(path):
        os.unlink(path)


def _trade(book, symbol, close_price, entry=100.0):
    pos = open_position(book, symbol, "long", 10.0, entry)
    close_position(book, pos.position_id, close_price)


def test_a_symbol_with_two_fresh_losses_is_locked_and_others_are_not(book):
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    _trade(book, "MSFT", 90.0)
    _trade(book, "NVDA", 110.0)
    locked, reason = symbol_lockout_active(book, "AAPL", losses=2, hours=72)
    assert locked and "all lost" in reason
    assert symbol_lockout_active(book, "MSFT", losses=2, hours=72) == (False, "")      # one loss only
    assert symbol_lockout_active(book, "NVDA", losses=2, hours=72) == (False, "")
    assert symbol_lockout_active(book, "TSLA", losses=2, hours=72) == (False, "")      # no history at all


def test_a_win_after_the_losses_frees_the_symbol(book):
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    assert symbol_lockout_active(book, "AAPL", losses=2, hours=72)[0] is True
    _trade(book, "AAPL", 120.0)
    assert symbol_lockout_active(book, "AAPL", losses=2, hours=72) == (False, "")


def test_the_module_constants_default_to_off(book):
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    assert guards.SYMBOL_LOCKOUT_LOSSES == 0
    assert symbol_lockout_active(book, "AAPL") == (False, "")
    assert active_symbol_lockouts(book) == []


def test_a_broken_book_means_not_locked_never_an_exception():
    assert symbol_lockout_active(object(), "AAPL", losses=2, hours=72) == (False, "")
    assert active_symbol_lockouts(object(), losses=2, hours=72) == []


def test_active_lockouts_lists_only_the_locked_symbols(book):
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    _trade(book, "MSFT", 90.0)
    rows = active_symbol_lockouts(book, losses=2, hours=72)
    assert [r["symbol"] for r in rows] == ["AAPL"] and rows[0]["streak"] == 2 and rows[0]["locked_until"]


# ------------------------------------------------------------------ the orchestrator entry path

def _orch(book, monkeypatch):
    """Two fresh losses also trip the portfolio-wide cooldown (2 in a row), which is checked first; switch it off here
    so these tests isolate the per-symbol lockout (they are complementary: the cooldown stops everything for 24h, the
    lockout stops one name for longer)."""
    import vinu_live.trade_plan.orchestrator as orch_mod
    from tests.test_trade_plan_orchestrator import _make_orchestrator
    monkeypatch.setattr(orch_mod, "COOLDOWN_LOSSES", 0)
    return _make_orchestrator(book)


def _entry_env(orch):
    from tests.test_trade_plan_orchestrator import _router
    get_mock, post_mock = _router(
        get_routes={"/broker/account": {"configured": True, "equity": 100000.0}, "/candles/AAPL": {"data": [{"close": 150.0}]},
                    "/broker/positions": []},
        post_routes={"/broker/order": {"status": "submitted", "order_id": "o1"}},
    )
    orch._http.get = get_mock
    orch._http.post = post_mock
    return post_mock


def test_the_orchestrator_refuses_a_new_entry_in_a_locked_symbol(book, monkeypatch):
    from tests.test_trade_plan_orchestrator import _SAMPLE_PLAN
    monkeypatch.setattr(guards, "SYMBOL_LOCKOUT_LOSSES", 2)
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    orch = _orch(book, monkeypatch)
    post = _entry_env(orch)
    action = asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))
    assert action["action"] == "entry_blocked_by_symbol_lockout" and "all lost" in action["reason"]
    post.assert_not_called()


def test_the_orchestrator_still_enters_an_unlocked_symbol_and_everything_when_off(book, monkeypatch):
    from tests.test_trade_plan_orchestrator import _SAMPLE_PLAN
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    orch = _orch(book, monkeypatch)
    _entry_env(orch)
    assert asyncio.run(orch._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))["action"] == "entered"   # off (default)
    monkeypatch.setattr(guards, "SYMBOL_LOCKOUT_LOSSES", 2)
    book2 = init_book(tempfile.NamedTemporaryFile(suffix=".db", delete=False).name)
    try:
        _trade(book2, "MSFT", 90.0)
        _trade(book2, "MSFT", 90.0)                       # a different symbol is locked, AAPL is not
        orch2 = _orch(book2, monkeypatch)
        _entry_env(orch2)
        assert asyncio.run(orch2._maybe_enter(_SAMPLE_PLAN, "AAPL", 150.0, 100000.0))["action"] == "entered"
    finally:
        book2.close()


# ------------------------------------------------------------------ the scheduler path

def _sched(tmp_path):
    s = LiveScheduler(LiveConfig(data_root=tmp_path, scheduler_entry_guards_enabled=True))
    s._http = MagicMock()
    s._http.get = AsyncMock(return_value=MagicMock(status_code=404))
    return s


def _instr(symbol, side, qty, current):
    return OrderInstruction(symbol=symbol, side=side, qty=qty, target_weight=0.1, current_qty=current, estimated_value=1000.0)


def test_the_scheduler_guard_blocks_an_increase_in_a_locked_symbol_but_never_a_reduce(tmp_path, monkeypatch):
    s = _sched(tmp_path)
    _trade(s._book, "AAPL", 90.0)
    _trade(s._book, "AAPL", 90.0)
    monkeypatch.setattr(guards, "SYMBOL_LOCKOUT_LOSSES", 2)
    buy, sell_reduce, other = _instr("AAPL", "buy", 10, 0), _instr("AAPL", "sell", 5, 10), _instr("MSFT", "buy", 10, 0)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(False, "")), \
         patch("vinu_live.scheduler.turbulence_active", AsyncMock(return_value=(False, ""))):
        kept, blocked = asyncio.run(s._apply_entry_guards([buy, sell_reduce, other]))
    assert kept == [sell_reduce, other]
    assert len(blocked) == 1 and blocked[0]["guard"] == "symbol_lockout" and blocked[0]["symbol"] == "AAPL"


def test_the_scheduler_guard_does_nothing_when_the_lockout_is_off(tmp_path):
    s = _sched(tmp_path)
    _trade(s._book, "AAPL", 90.0)
    _trade(s._book, "AAPL", 90.0)
    with patch("vinu_live.scheduler.cooldown_active", return_value=(False, "")), \
         patch("vinu_live.scheduler.turbulence_active", AsyncMock(return_value=(False, ""))):
        kept, blocked = asyncio.run(s._apply_entry_guards([_instr("AAPL", "buy", 10, 0)]))
    assert len(kept) == 1 and blocked == []


# ------------------------------------------------------------------ the route

def test_route_lists_current_lockouts(tmp_path, monkeypatch):
    book = init_book(str(tmp_path / "trade_plan_book.db"))
    _trade(book, "AAPL", 90.0)
    _trade(book, "AAPL", 90.0)
    book.close()
    config = LiveConfig(data_root=tmp_path)
    with patch("vinu_live.server.app.load_config", return_value=config):
        client = TestClient(create_app())
        off = client.get("/live/lockouts").json()
        assert off["enabled"] is False and off["lockouts"] == [] and off["count"] == 0
        monkeypatch.setattr(guards, "SYMBOL_LOCKOUT_LOSSES", 2)
        on = client.get("/live/lockouts").json()
    assert on["enabled"] is True and on["count"] == 1 and on["lockouts"][0]["symbol"] == "AAPL" and on["lockouts"][0]["locked_until"]


def test_route_with_no_book_is_a_clean_empty_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(guards, "SYMBOL_LOCKOUT_LOSSES", 2)
    with patch("vinu_live.server.app.load_config", return_value=LiveConfig(data_root=tmp_path)):
        body = TestClient(create_app()).get("/live/lockouts").json()
    assert body["enabled"] is True and body["lockouts"] == []
