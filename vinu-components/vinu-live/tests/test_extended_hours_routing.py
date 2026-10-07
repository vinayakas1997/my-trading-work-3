"""Outside the regular session the broker takes only limit orders and no stop leg. The live code used to choose "market"
(always for exits), which the order guard refuses, so an exit at night would have been blocked (problem log O9)."""

from __future__ import annotations

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from vinu_live.trade_plan.guards import EXTENDED_MARKETABLE_BPS, extended_hours_route

NY = ZoneInfo("America/New_York")
REGULAR = datetime(2026, 10, 7, 11, 0, tzinfo=NY).timestamp()       # Wednesday 11:00
OVERNIGHT = datetime(2026, 10, 7, 23, 0, tzinfo=NY).timestamp()
PREMARKET = datetime(2026, 10, 8, 5, 0, tzinfo=NY).timestamp()
WEEKEND = datetime(2026, 10, 10, 12, 0, tzinfo=NY).timestamp()      # Saturday: closed


def _route(side="sell", order_type="market", limit=None, ref=100.0, now=OVERNIGHT, http=None):
    return asyncio.run(extended_hours_route(http or MagicMock(), "http://x", "SPY", side, order_type, limit, reference_price=ref, now=now))


@pytest.mark.parametrize("now", [REGULAR, WEEKEND])
def test_the_regular_session_and_the_weekend_gap_change_nothing(now):
    assert _route(now=now) == ("market", None, False)


@pytest.mark.parametrize("now", [OVERNIGHT, PREMARKET])
def test_an_exit_at_night_becomes_a_limit_a_little_below_the_price(now):
    order_type, limit, extended = _route(side="sell", now=now)
    assert (order_type, extended) == ("limit", True)
    assert limit == pytest.approx(100.0 * (1 - EXTENDED_MARKETABLE_BPS / 10_000), abs=0.01)


def test_a_buy_at_night_is_limited_a_little_above_the_price():
    _, limit, _ = _route(side="buy")
    assert limit > 100.0


def test_a_limit_the_caller_already_chose_is_kept():
    assert _route(side="buy", order_type="limit", limit=99.5) == ("limit", 99.5, True)


def test_with_no_price_the_order_is_left_for_the_guard_to_refuse_not_invented():
    http = MagicMock()
    http.get = AsyncMock(side_effect=ConnectionError("down"))
    assert _route(ref=None, http=http) == ("market", None, True)


def test_the_live_quote_mid_is_used_when_the_caller_has_no_price():
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = {"ok": True, "mid": 50.0, "spread_bps": 4.0}
    http = MagicMock()
    http.get = AsyncMock(return_value=r)
    order_type, limit, _ = _route(side="sell", ref=None, http=http)
    assert order_type == "limit" and limit < 50.0


def test_the_orchestrator_sends_a_limit_and_no_stop_leg_at_night(tmp_path, monkeypatch):
    from vinu_live.config import LiveConfig
    from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator

    monkeypatch.setattr("vinu_live.trade_plan.guards._now", lambda: OVERNIGHT)
    o = TradePlanOrchestrator(LiveConfig(data_root=tmp_path))
    sent = {}

    async def _post(url, json=None, **kw):
        sent.update(json)
        r = MagicMock()
        r.status_code = 200
        r.json.return_value = {"status": "submitted"}
        return r

    o._http = MagicMock()
    o._http.post = AsyncMock(side_effect=_post)
    q = MagicMock()
    q.status_code = 200
    q.json.return_value = {"ok": True, "mid": 100.0, "spread_bps": 3.0}
    o._http.get = AsyncMock(return_value=q)
    asyncio.run(o._submit_order("SPY", "sell", 1.0, reduce_only=True, stop_loss_price=90.0))
    assert sent["order_type"] == "limit" and sent["limit_price"] < 100.0 and "stop_loss_price" not in sent


def test_the_scheduler_sends_a_limit_exit_at_night(monkeypatch):
    from vinu_live.config import LiveConfig
    from vinu_live.execution import ExecutionPlan, ExecutionSlice
    from vinu_live.scheduler import LiveScheduler

    monkeypatch.setattr("vinu_live.trade_plan.guards._now", lambda: OVERNIGHT)
    monkeypatch.setattr("vinu_live.scheduler.asyncio.sleep", AsyncMock())
    s = LiveScheduler(LiveConfig(scheduler_exits_exempt_from_halts=True))
    s._http = MagicMock()
    r = MagicMock()
    r.status_code = 404
    s._http.get = AsyncMock(return_value=r)
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {}
    s._http.post = AsyncMock(return_value=ok)
    plan = ExecutionPlan([ExecutionSlice(symbol="AAPL", side="sell", qty=10.0, slice_number=1, total_slices=1, reduce_only=True)])
    asyncio.run(s._execute_plan(plan, prices={"AAPL": 150.0}))
    sent = s._http.post.call_args_list[0].kwargs["json"]
    assert sent["order_type"] == "limit" and sent["limit_price"] < 150.0 and sent["reduce_only"] is True
