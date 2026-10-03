"""logic-audit-2026-10-02 A5 (the-inconsistencies-v2, Phase 4): on the scheduler path a halt or a
spread / event gate must not trap a position. Opt-in `scheduler_exits_exempt_from_halts` (default off).

Instructions that only shrink or close a position are tagged `reduces_exposure`, their slices carry
`reduce_only`, go as market orders with `reduce_only=true`, and skip the halt / spread / event stops.
Anything that increases exposure is gated exactly as before, in both modes.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan, ExecutionSlice, plan_twap, plan_vwap
from vinu_live.scheduler import LiveScheduler
from vinu_live.signal_translator import OrderInstruction


def _sched(exempt: bool, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(scheduler_exits_exempt_from_halts=exempt, **cfg))
    s._http = MagicMock()
    return s


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def _slice(side, reduce_only, symbol="AAPL", n=1, total=1):
    return ExecutionSlice(symbol=symbol, side=side, qty=10.0, slice_number=n, total_slices=total, reduce_only=reduce_only)


def _halted(monkeypatch, reason="kill switch"):
    monkeypatch.setattr("vinu_live.scheduler.halt_reason", AsyncMock(return_value=reason))


def _no_sleep(monkeypatch):
    monkeypatch.setattr("vinu_live.scheduler.asyncio.sleep", AsyncMock())


def _posts(s):
    return [c.kwargs["json"] for c in s._http.post.call_args_list]


# ------------------------------------------------------------------ plumbing

def test_flag_defaults_off_and_reads_env(monkeypatch):
    assert LiveConfig().scheduler_exits_exempt_from_halts is False
    monkeypatch.setenv("VINU_LIVE_SCHEDULER_EXITS_EXEMPT_FROM_HALTS", "true")
    assert LiveConfig.from_env().scheduler_exits_exempt_from_halts is True


@pytest.mark.parametrize("planner", [plan_twap, plan_vwap])
def test_planners_carry_reduces_exposure_onto_every_slice(planner):
    instrs = [
        OrderInstruction("AAPL", "sell", 12.0, 0.0, 20.0, 1000.0, reduces_exposure=True),
        OrderInstruction("MSFT", "buy", 6.0, 0.1, 0.0, 1000.0),
    ]
    plan = planner(instrs, n_slices=3)
    assert all(s.reduce_only for s in plan.slices if s.symbol == "AAPL")
    assert not any(s.reduce_only for s in plan.slices if s.symbol == "MSFT")


def test_default_instruction_is_not_reducing():
    assert OrderInstruction("A", "sell", 1.0, 0.0, 5.0, 10.0).reduces_exposure is False


# ------------------------------------------------------------------ _execute_plan: kill switch / halt

def test_halt_still_stops_everything_when_off(monkeypatch):
    _halted(monkeypatch)
    s = _sched(False)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    out = asyncio.run(s._execute_plan(ExecutionPlan([_slice("sell", True)])))
    assert out == [] and not _posts(s)


def test_halt_lets_exits_through_and_blocks_increases_when_on(monkeypatch):
    _halted(monkeypatch)
    _no_sleep(monkeypatch)
    s = _sched(True)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    plan = ExecutionPlan([_slice("sell", True, "AAPL"), _slice("buy", False, "MSFT")])
    out = asyncio.run(s._execute_plan(plan))
    posts = _posts(s)
    assert [p["symbol"] for p in posts] == ["AAPL"]
    assert posts[0]["side"] == "sell" and posts[0]["reduce_only"] is True and posts[0]["order_type"] == "market"
    assert [o["symbol"] for o in out] == ["AAPL"]


def test_halt_with_only_increases_still_places_nothing_when_on(monkeypatch):
    _halted(monkeypatch)
    s = _sched(True)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock()
    assert asyncio.run(s._execute_plan(ExecutionPlan([_slice("buy", False)]))) == []
    s._http.post.assert_not_called()


def test_a_halt_appearing_mid_plan_drops_later_increases_but_keeps_exits(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    async def _halt(*a, **k):
        calls["n"] += 1
        return None if calls["n"] == 1 else "breaker engaged"   # clear at start, engaged after slice 1

    monkeypatch.setattr("vinu_live.scheduler.halt_reason", _halt)
    s = _sched(True)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    plan = ExecutionPlan([
        _slice("buy", False, "AAA", 1, 3), _slice("buy", False, "BBB", 2, 3), _slice("sell", True, "CCC", 3, 3),
    ])
    asyncio.run(s._execute_plan(plan))
    assert [p["symbol"] for p in _posts(s)] == ["AAA", "CCC"]   # BBB dropped, the exit still goes


def test_a_halt_appearing_mid_plan_still_breaks_the_whole_plan_when_off(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    async def _halt(*a, **k):
        calls["n"] += 1
        return None if calls["n"] == 1 else "breaker engaged"

    monkeypatch.setattr("vinu_live.scheduler.halt_reason", _halt)
    s = _sched(False)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    plan = ExecutionPlan([_slice("buy", False, "AAA", 1, 2), _slice("sell", True, "CCC", 2, 2)])
    asyncio.run(s._execute_plan(plan))
    assert [p["symbol"] for p in _posts(s)] == ["AAA"]


# ------------------------------------------------------------------ _execute_plan: spread / event gates

def _quote_get(spread=None, blackout=False):
    async def _get(url, params=None, **kw):
        if "/stock/quote" in url and spread is not None:
            return _resp(200, {"ok": True, "spread_bps": spread})
        if "/stock/events" in url and blackout:
            return _resp(200, {"blackout": True, "events": [{"title": "EARNINGS"}]})
        return _resp(404)
    return _get


@pytest.mark.parametrize("gate", ["spread", "event"])
def test_gates_do_not_hold_back_an_exit_when_on_but_still_hold_back_an_increase(monkeypatch, gate):
    _no_sleep(monkeypatch)
    s = _sched(True)
    s._http.get = AsyncMock(side_effect=_quote_get(spread=500.0 if gate == "spread" else None, blackout=gate == "event"))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    plan = ExecutionPlan([_slice("sell", True, "AAPL"), _slice("buy", False, "MSFT")])
    out = asyncio.run(s._execute_plan(plan, prices={"AAPL": 150.0, "MSFT": 300.0}))
    assert [p["symbol"] for p in _posts(s)] == ["AAPL"]
    assert {o["symbol"]: o["status"] for o in out} == {"AAPL": "submitted", "MSFT": "skipped"}
    assert _posts(s)[0]["order_type"] == "market"   # never a resting limit for an exit


@pytest.mark.parametrize("gate", ["spread", "event"])
def test_gates_still_skip_an_exit_when_off(monkeypatch, gate):
    _no_sleep(monkeypatch)
    s = _sched(False)
    s._http.get = AsyncMock(side_effect=_quote_get(spread=500.0 if gate == "spread" else None, blackout=gate == "event"))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    out = asyncio.run(s._execute_plan(ExecutionPlan([_slice("sell", True)])))
    assert out[0]["status"] == "skipped" and not _posts(s)


def test_reduce_only_is_not_sent_when_off(monkeypatch):
    _no_sleep(monkeypatch)
    s = _sched(False)
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    asyncio.run(s._execute_plan(ExecutionPlan([_slice("sell", True)])))
    assert "reduce_only" not in _posts(s)[0]


def test_wide_spread_exit_goes_market_not_limit(monkeypatch):
    """10 bps is inside the gate but over the routing budget: an entry would route limit, an exit must not."""
    _no_sleep(monkeypatch)
    s = _sched(True)
    s._http.get = AsyncMock(side_effect=_quote_get(spread=10.0))
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    asyncio.run(s._execute_plan(ExecutionPlan([_slice("sell", True)]), prices={"AAPL": 150.0}))
    p = _posts(s)[0]
    assert p["order_type"] == "market" and "limit_price" not in p


# ------------------------------------------------------------------ the whole cycle under a breaker HALT

def _cycle_sched(exempt, monkeypatch):
    from vinu_live.breaker.engine import BreakerVerdict
    s = _sched(exempt)

    async def _get(url, params=None, **kw):
        if "/portfolio/state" in url:
            # AAPL cut to zero (a sell of the 20 held), MSFT opened (a buy)
            return _resp(200, {"weights": [
                {"symbol": "AAPL", "target_weight": 0.0}, {"symbol": "MSFT", "target_weight": 0.1}]})
        if "/broker/positions" in url:
            return _resp(200, [{"symbol": "AAPL", "qty": 20.0}])
        if "/broker/account" in url:
            return _resp(200, {"configured": True, "equity": 100_000.0})
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    s._check_breaker = AsyncMock(return_value=(BreakerVerdict.HALT, "daily loss limit"))
    monkeypatch.setattr("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None))
    _no_sleep(monkeypatch)
    return s


def test_breaker_halt_blocks_everything_when_off(monkeypatch):
    s = _cycle_sched(False, monkeypatch)
    r = asyncio.run(s.cycle())
    assert r["status"] == "halted_by_breaker" and "submitted" not in r
    s._http.post.assert_not_called()


def test_breaker_halt_still_executes_the_sell_but_not_the_buy_when_on(monkeypatch):
    s = _cycle_sched(True, monkeypatch)
    r = asyncio.run(s.cycle())
    assert r["status"] == "halted_by_breaker" and r["exits_only"] is True
    posts = _posts(s)
    assert posts and all(p["side"] == "sell" and p["symbol"] == "AAPL" and p["reduce_only"] is True for p in posts)
    assert not any(p["symbol"] == "MSFT" for p in posts)
