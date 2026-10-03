"""Phase 3 of the-inconsistencies-v2 plan: the runtime edge recorder wired into the
vinu-live consumption points (scheduler, orchestrator plan fetch, halt checks).

Pins the two things that matter next to order flow:
1. each instrumented edge records the right status for each situation
   (received / empty / missing), including the failures that used to leave
   no trace (a non-200 plan list looked identical to "no plans");
2. recording never changes behavior: same cycle result, same exceptions,
   and a broken or absent recorder is invisible to the caller.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_live.book.positions import init_book
from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.live_decision.storage import open_position
from vinu_live.scheduler import LiveScheduler
from vinu_live.trade_plan.correlation_monitor_store import CorrelationMonitorStore
from vinu_live.trade_plan.guards import halt_reason
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue


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


def _resp(status_code=200, json_body=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body if json_body is not None else {}
    r.raise_for_status = MagicMock()
    if status_code >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return r


def _scheduler(tmp_path, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path / "live", twap_slices=1, **cfg))
    s._http = MagicMock()
    return s


def _wire(s, *, portfolio=None, portfolio_raises=None, positions=None, halt_status=200):
    async def _get(url, **kwargs):
        if "/portfolio/state" in url:
            if portfolio_raises:
                raise portfolio_raises
            return _resp(json_body=portfolio if portfolio is not None else
                         {"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
        if "/agent/broker/positions" in url:
            return _resp(json_body=positions if positions is not None else [])
        if "/agent/broker/account" in url:
            return _resp(json_body={"configured": False})
        if "/agent/broker/status" in url:
            return _resp(status_code=halt_status, json_body={"halted": False})
        if "/stock/quote/" in url or "/stock/events/" in url:
            return _resp(status_code=404)
        if "/candles/" in url:
            return _resp(json_body={"data": [{"close": 150.0}]})
        raise AssertionError(f"unexpected GET: {url}")

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(status_code=200))


def _cycle(s):
    with patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
        return asyncio.run(s.cycle())


# ------------------------------------------------------------------ scheduler edges

def test_a_normal_cycle_records_the_edges_it_consumed(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s)
    out = _cycle(s)
    assert out["status"] == "ok"
    assert _state("portfolio.state->live.scheduler")["status"] == "received"
    assert _state("live_decision.executes->live.scheduler")["status"] == "empty"  # nothing pending or open
    assert _state("breaker.limits->live.scheduler")["status"] == "received"
    assert _state("halt_flag->live.scheduler")["status"] == "received"


def test_an_empty_portfolio_is_recorded_as_empty_not_received(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s, portfolio={"status": "empty", "weights": []})
    _cycle(s)
    assert _state("portfolio.state->live.scheduler")["status"] == "empty"


def test_a_failed_portfolio_read_is_recorded_missing_and_still_aborts_the_cycle(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s, portfolio_raises=ConnectionError("portfolio down"))
    out = _cycle(s)
    assert out["status"] == "failed" and "portfolio down" in out["error"]  # behavior unchanged
    st = _state("portfolio.state->live.scheduler")
    assert st["status"] == "missing" and "portfolio down" in st["last_detail"]


def test_a_non_200_kill_switch_status_is_recorded_missing(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s, halt_status=503)
    _cycle(s)
    st = _state("halt_flag->live.scheduler")
    assert st["status"] == "missing" and "503" in st["last_detail"]


def test_an_open_live_decision_position_is_recorded_received(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s)
    open_position(s._live_decision_backend, ticker="AAPL", strategy_id="s1", position_size=0.02,
                  opened_bar_ts=1, trigger_id="t1")
    _cycle(s)
    assert _state("live_decision.executes->live.scheduler")["status"] == "received"


def test_strategy_config_fetch_is_recorded_both_ways(tmp_path):
    s = _scheduler(tmp_path)
    s._http.get = AsyncMock(return_value=_resp(json_body={"live_decision_position_size": 0.05}))
    assert asyncio.run(s._fetch_strategy_config("s1")) is not None
    assert _state("strategy.config->live.scheduler")["status"] == "received"
    s._http.get = AsyncMock(return_value=_resp(status_code=404))
    assert asyncio.run(s._fetch_strategy_config("s1")) is None
    st = _state("strategy.config->live.scheduler")
    assert st["status"] == "missing" and "404" in st["last_detail"]
    s._http.get = AsyncMock(side_effect=ConnectionError("down"))
    assert asyncio.run(s._fetch_strategy_config("s1")) is None
    assert _state("strategy.config->live.scheduler")["n_missing"] == 2


def test_maturity_status_is_recorded_when_the_opt_in_flag_is_on(tmp_path):
    s = _scheduler(tmp_path, risk_gatekeeper_maturity_scaling_enabled=True)
    with patch("vinu_live.scheduler.fetch_maturity_status", AsyncMock(return_value=None)):
        asyncio.run(s._maturity_scaled_limits())
    assert _state("maturity.status->live.limits")["status"] == "missing"
    with patch("vinu_live.scheduler.fetch_maturity_status", AsyncMock(return_value={"tier": "mature"})):
        asyncio.run(s._maturity_scaled_limits())
    assert _state("maturity.status->live.limits")["status"] == "received"


def test_maturity_is_not_recorded_when_the_flag_is_off(tmp_path):
    s = _scheduler(tmp_path)
    asyncio.run(s._maturity_scaled_limits())
    assert _state("maturity.status->live.limits") is None


# ------------------------------------------------------------------ orchestrator edges

def _orchestrator() -> TradePlanOrchestrator:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    book = init_book(path)
    orch = TradePlanOrchestrator(
        LiveConfig(), book=book, rebalance_queue=RebalanceRequestQueue(":memory:"),
        correlation_store=CorrelationMonitorStore(":memory:"),
    )
    orch._http = MagicMock()
    orch._test_cleanup = (book, path)
    return orch


def _cleanup(orch):
    book, path = orch._test_cleanup
    book.close()
    if os.path.exists(path):
        os.unlink(path)


def test_plan_list_failures_are_no_longer_indistinguishable_from_no_plans():
    orch = _orchestrator()
    try:
        edge = "research.active_trade_plans->live.orchestrator"
        orch._http.get = AsyncMock(return_value=_resp(status_code=500))
        assert asyncio.run(orch._fetch_active_trade_plans()) == []
        st = _state(edge)
        assert st["status"] == "missing" and "500" in st["last_detail"]

        orch._http.get = AsyncMock(return_value=_resp(json_body=[]))
        assert asyncio.run(orch._fetch_active_trade_plans()) == []
        assert _state(edge)["status"] == "empty"

        orch._http.get = AsyncMock(side_effect=ConnectionError("research down"))
        assert asyncio.run(orch._fetch_active_trade_plans()) == []
        assert _state(edge)["status"] == "missing" and "research down" in _state(edge)["last_detail"]
        assert _state(edge)["n_missing"] == 2
    finally:
        _cleanup(orch)


def test_orchestrator_halt_check_records_its_own_edge():
    orch = _orchestrator()
    try:
        orch._http.get = AsyncMock(return_value=_resp(json_body={"halted": False}))
        asyncio.run(orch._is_trading_halted())
        assert _state("halt_flag->live.orchestrator")["status"] == "received"
        assert _state("halt_flag->live.scheduler") is None  # the other executor's edge is separate
    finally:
        _cleanup(orch)


# ------------------------------------------------------------------ halt_reason directly

def test_halt_reason_records_only_when_given_an_edge_id():
    http = MagicMock()
    http.get = AsyncMock(return_value=_resp(json_body={"halted": True}))
    assert asyncio.run(halt_reason(http, "http://agent")) is not None
    assert rec.resolve_edge_status_store().list_states() == []  # no edge id -> nothing recorded
    assert asyncio.run(halt_reason(http, "http://agent", edge_id="e")) is not None  # a HALT is still "received"
    assert _state("e")["status"] == "received"


def test_halt_reason_exception_is_missing_and_still_fails_open():
    http = MagicMock()
    http.get = AsyncMock(side_effect=ConnectionError("agent down"))
    assert asyncio.run(halt_reason(http, "http://agent", edge_id="e")) is None  # behavior unchanged: fail-open
    assert _state("e")["status"] == "missing" and "agent down" in _state("e")["last_detail"]


# ------------------------------------------------------------------ recording never changes behavior

def test_a_broken_recorder_changes_nothing(tmp_path):
    s = _scheduler(tmp_path)
    _wire(s)
    baseline = _cycle(s)

    class _Broken:
        def record(self, *a, **k):
            raise RuntimeError("edge db corrupted")

    s2 = _scheduler(tmp_path)
    _wire(s2)
    with patch.object(rec, "resolve_edge_status_store", return_value=_Broken()):
        out = _cycle(s2)
    assert out["status"] == baseline["status"] == "ok"
    assert out.get("n_instructions") == baseline.get("n_instructions")


def test_no_recording_root_means_no_files_and_no_change(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_EDGE_DATA_ROOT", raising=False)
    rec.reset_for_tests()
    s = _scheduler(tmp_path)
    _wire(s)
    assert _cycle(s)["status"] == "ok"
    assert not list(tmp_path.rglob("pipeline_edges.db"))
