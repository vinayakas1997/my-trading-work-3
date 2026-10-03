"""Phase 3 extension: the runtime edge recorder wired into the rest of the vinu-live consumption points
(approval worker, scheduler guards / precondition / reduce-only / drift notice / entry price / unsized EXECUTEs,
poller stop rules and stuck-trigger notice). Each site must record the right status for each situation, and
recording must never change what the caller does.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan, ExecutionSlice
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.schema import LiveDecisionRecord
from vinu_live.live_decision.storage import LiveDecisionBackend, open_position, record_live_decision
from vinu_live.scheduler import LiveScheduler
from vinu_live.signal_translator import OrderInstruction
from vinu_live.trade_plan_approval_worker import TradePlanApprovalWorker


@pytest.fixture(autouse=True)
def _recorder_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


def _state(edge_id):
    store = rec.resolve_edge_status_store()
    return store.get_state(edge_id) if store else None


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.raise_for_status = MagicMock()
    if status >= 400:
        r.raise_for_status.side_effect = RuntimeError(f"HTTP {status}")
    return r


def _sched(tmp_path, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path / "live", twap_slices=1, **cfg))
    s._http = MagicMock()
    return s


def _status(edge_id):
    st = _state(edge_id)
    return st["status"] if st else None


# ------------------------------------------------------------------ approval worker

def _worker(get):
    w = TradePlanApprovalWorker.__new__(TradePlanApprovalWorker)
    w._research_api = "http://r"
    w._http = MagicMock()
    w._http.get = get
    return w


E_APPROVAL = "research.created_trade_plans->live.approval_worker"


@pytest.mark.parametrize("get,expected,plans", [
    (AsyncMock(return_value=_resp(200, [{"artifact_id": "a"}])), "received", [{"artifact_id": "a"}]),
    (AsyncMock(return_value=_resp(200, [])), "empty", []),
    (AsyncMock(return_value=_resp(503)), "missing", []),
    (AsyncMock(side_effect=ConnectionError("down")), "missing", []),
])
def test_approval_worker_listing_is_recorded_and_returns_what_it_always_did(get, expected, plans):
    assert asyncio.run(_worker(get)._list_created_trade_plans()) == plans
    assert _status(E_APPROVAL) == expected


# ------------------------------------------------------------------ scheduler guards

def _instr(symbol="AAPL"):
    return OrderInstruction(symbol=symbol, side="buy", qty=10.0, target_weight=0.1, current_qty=0.0, estimated_value=1000.0)


def test_entry_guards_record_cooldown_freshness_and_turbulence_inputs(tmp_path):
    s = _sched(tmp_path, scheduler_entry_guards_enabled=True)
    s._last_price_ts["AAPL"] = __import__("time").time() - 3600
    s._http.get = AsyncMock(return_value=_resp(200, {"data": [{"close": 100.0 + i} for i in range(20)]}))
    asyncio.run(s._apply_entry_guards([_instr("AAPL")]))
    assert _status("guard.cooldown->live.scheduler") == "received"
    assert _status("guard.data_freshness->live.scheduler") == "received"
    assert _status("guard.turbulence->live.scheduler") == "received"


def test_a_symbol_with_no_bar_timestamp_is_recorded_as_missing_freshness(tmp_path):
    s = _sched(tmp_path, scheduler_entry_guards_enabled=True)
    s._http.get = AsyncMock(return_value=_resp(200, {"data": []}))
    asyncio.run(s._apply_entry_guards([_instr("AAPL")]))
    st = _state("guard.data_freshness->live.scheduler")
    assert st["status"] == "missing" and "no bar timestamp" in st["last_detail"]
    assert _status("guard.turbulence->live.scheduler") == "missing"          # no closes came back either


@pytest.mark.parametrize("answer,expected", [
    (_resp(200, {"data": [{"close": 10.0}]}), "received"), (_resp(200, {"data": []}), "missing"), (_resp(500), "missing"),
])
def test_turbulence_inputs_are_recorded_per_answer(tmp_path, answer, expected):
    s = _sched(tmp_path)
    s._http.get = AsyncMock(return_value=answer)
    asyncio.run(s._fetch_recent_closes("AAPL"))
    assert _status("guard.turbulence->live.scheduler") == expected
    s2 = _sched(tmp_path / "b")
    s2._http.get = AsyncMock(side_effect=ConnectionError("x"))
    assert asyncio.run(s2._fetch_recent_closes("AAPL")) == []
    assert _status("guard.turbulence->live.scheduler") == "missing"


# ------------------------------------------------------------------ reduce-only and precondition

def _slice(side="sell", reduce_only=True):
    return ExecutionSlice(symbol="AAPL", side=side, qty=10.0, slice_number=1, total_slices=1, reduce_only=reduce_only)


def _run_plan(s, plan, post):
    s._http.get = AsyncMock(return_value=_resp(404))
    s._http.post = AsyncMock(side_effect=post)
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        return asyncio.run(s._execute_plan(plan, {"AAPL": 100.0}))


def test_a_reduce_only_order_is_recorded_received_when_accepted_and_missing_when_refused(tmp_path):
    s = _sched(tmp_path, scheduler_exits_exempt_from_halts=True)
    _run_plan(s, ExecutionPlan([_slice()]), AsyncMock(return_value=_resp(200, {"status": "submitted"})))
    assert _status("order.reduce_only->live.scheduler") == "received"
    _run_plan(s, ExecutionPlan([_slice()]), AsyncMock(return_value=_resp(200, {"status": "rejected", "reason": "x"})))
    st = _state("order.reduce_only->live.scheduler")
    assert st["status"] == "missing" and "rejected" in st["last_detail"]


def test_an_increase_never_touches_the_reduce_only_edge(tmp_path):
    s = _sched(tmp_path, scheduler_exits_exempt_from_halts=True)
    _run_plan(s, ExecutionPlan([_slice("buy", reduce_only=False)]), AsyncMock(return_value=_resp(200, {"status": "submitted"})))
    assert _state("order.reduce_only->live.scheduler") is None


def _decision(tmp_path, held):
    backend = LiveDecisionBackend(str(tmp_path / "live" / "live_decision.db"))
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="s", trigger_id="t", bar_ts=1, decision="EXECUTE", precondition_held=held, reasoning="r", raw_content="c"))
    backend.close()


@pytest.mark.parametrize("held,expected", [(True, "received"), (False, "received"), (None, "missing")])
def test_precondition_held_is_recorded_missing_only_when_the_agent_did_not_state_it(tmp_path, held, expected):
    s = _sched(tmp_path)
    _decision(tmp_path, held)
    s._http.get = AsyncMock(return_value=_resp(200, {"live_decision_position_size": 0.05}))
    asyncio.run(s._fetch_live_decision_weights("c1"))
    assert _status("precondition_held->live.scheduler") == expected


# ------------------------------------------------------------------ notices

@pytest.mark.parametrize("answer,expected", [(_resp(200, {}), "received"), (_resp(500), "missing")])
def test_the_drift_notice_is_recorded(tmp_path, answer, expected):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=answer)
    asyncio.run(s._notify_target_weight_drift({"symbol": "AAPL", "expected_qty": 1, "actual_qty": 0, "drift_pct": 100}))
    assert _status("reconciliation_drift->agent.notify") == expected
    s._http.post = AsyncMock(side_effect=ConnectionError("down"))
    asyncio.run(s._notify_target_weight_drift({"symbol": "AAPL"}))
    assert _status("reconciliation_drift->agent.notify") == "missing"


def _poller(tmp_path):
    backend = LiveDecisionBackend(str(tmp_path / "live" / "ld.db"))
    p = CandleClosePoller(LiveConfig(data_root=tmp_path / "live"), backend=backend)
    p._http = MagicMock()
    return p, backend


def test_the_stuck_trigger_notice_is_recorded(tmp_path):
    p, _ = _poller(tmp_path)
    p._http.post = AsyncMock(return_value=_resp(200, {}))
    asyncio.run(p._notify_stuck_decision("AAPL", "s", "t1", "gave up"))
    assert _status("live_decision.stuck_trigger->agent.notify") == "received"
    p._http.post = AsyncMock(return_value=_resp(503))
    asyncio.run(p._notify_stuck_decision("AAPL", "s", "t1", "gave up"))
    assert _status("live_decision.stuck_trigger->agent.notify") == "missing"


# ------------------------------------------------------------------ poller stop rules, entry price, unsized

def _bars(close=100.0):
    import pandas as pd
    return pd.DataFrame({"close": [close]})


@pytest.mark.parametrize("strat,expected", [
    ({"name": "s", "live_decision_stop_pct": 0.05}, "received"),
    ({"name": "s", "live_decision_max_hold_bars": 10}, "received"),
    ({"name": "s"}, "empty"),
    ({"name": "s", "live_decision_stop_pct": 0.0, "live_decision_max_hold_bars": 0}, "empty"),
])
def test_stop_rules_are_recorded_received_only_when_a_rule_is_configured(tmp_path, strat, expected):
    p, backend = _poller(tmp_path)
    open_position(backend, ticker="AAPL", strategy_id="s", position_size=0.05, opened_bar_ts=1, trigger_id="t")
    p._apply_position_rules("AAPL", "1d", 100, _bars(), [strat])
    assert _status("strategy.stop_rules->live.poller") == expected


def test_entry_price_stamping_is_recorded(tmp_path):
    s = _sched(tmp_path)
    s._record_live_decision_entry_prices({"AAPL": 100.0})
    assert _status("live_decision.entry_price<-live.scheduler") == "empty"            # nothing open
    open_position(s._live_decision_backend, ticker="AAPL", strategy_id="s", position_size=0.05, opened_bar_ts=1, trigger_id="t")
    s._record_live_decision_entry_prices({"AAPL": 100.0})
    st = _state("live_decision.entry_price<-live.scheduler")
    assert st["status"] == "received" and "stamped 1" in st["last_detail"]
    s._record_live_decision_entry_prices({"AAPL": 100.0})                             # write-once: nothing left to stamp
    assert _status("live_decision.entry_price<-live.scheduler") == "empty"


def test_unsized_executes_are_recorded_each_cycle(tmp_path):
    s = _sched(tmp_path)

    async def _get(url, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"status": "empty", "weights": []})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    asyncio.run(s.cycle())
    assert _status("live_decision.unsized_executes->live.api") == "empty"


# ------------------------------------------------------------------ recording never changes behavior

def test_a_broken_recorder_is_invisible_to_the_sites(tmp_path, monkeypatch):
    monkeypatch.setattr(rec, "resolve_edge_status_store", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("recorder down")))
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=_resp(200, {}))
    asyncio.run(s._notify_target_weight_drift({"symbol": "AAPL"}))
    s._record_live_decision_entry_prices({"AAPL": 1.0})
    assert asyncio.run(_worker(AsyncMock(return_value=_resp(200, [])))._list_created_trade_plans()) == []
