"""Phase 5 groundwork for execution parity (the-inconsistencies-v2): the scheduler's order ledger, and the
fix that stops a REFUSED order being reported as "submitted".

Bug found while building it: POST /agent/broker/order answers HTTP 200 even when OrderGuard refuses the order
(`{"status": "rejected", ...}`) or the broker call fails (`{"status": "error"}`); the scheduler reported every
HTTP < 400 as "submitted" without reading the body (the orchestrator does read it).
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan, ExecutionSlice
from vinu_live.execution_log import ExecutionLog
from vinu_live.scheduler import LiveScheduler
from vinu_live.server.app import create_app


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def _sched(tmp_path, **cfg) -> LiveScheduler:
    s = LiveScheduler(LiveConfig(data_root=tmp_path, **cfg))
    s._http = MagicMock()

    async def _get(url, params=None, **kw):
        if "/stock/quote" in url:
            return _resp(200, {"ok": True, "spread_bps": 3.1})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    return s


def _slice(side="buy", n=1, total=1, symbol="AAPL", reduce_only=False):
    return ExecutionSlice(symbol=symbol, side=side, qty=10.0, slice_number=n, total_slices=total, reduce_only=reduce_only)


def _run(s, plan, prices=None):
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), \
         patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        return asyncio.run(s._execute_plan(plan, prices or {"AAPL": 187.2}))


# ------------------------------------------------------------------ the outcome fix

@pytest.mark.parametrize("body,expected", [
    ({"status": "submitted", "order_id": "o1", "broker_status": "accepted"}, "submitted"),
    ({"status": "rejected", "reason": "daily order cap", "reason_code": "daily_cap"}, "rejected"),
    ({"status": "pending_confirmation", "message": "needs a human"}, "pending_confirmation"),
    ({"status": "error", "error": "broker timeout"}, "error"),
    ({}, "submitted"),                                   # unknown / empty body keeps the old reading
    ({"status": "something_new"}, "submitted"),
])
def test_http_200_with_a_refusal_body_is_not_reported_as_submitted(tmp_path, body, expected):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=_resp(200, body))
    (out,) = _run(s, ExecutionPlan([_slice()]))
    assert out["status"] == expected
    if expected in ("rejected", "pending_confirmation", "error"):
        assert out["reason"]


def test_a_rejection_reason_carries_its_code(tmp_path):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "rejected", "reason": "daily order cap", "reason_code": "daily_cap"}))
    (out,) = _run(s, ExecutionPlan([_slice()]))
    assert out["reason"] == "daily order cap [daily_cap]"


def test_http_error_and_unreadable_body_and_exception(tmp_path):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=_resp(500))
    assert _run(s, ExecutionPlan([_slice()]))[0]["status"] == "failed"
    bad = MagicMock(status_code=200)
    bad.json.side_effect = ValueError("not json")
    s._http.post = AsyncMock(return_value=bad)
    assert _run(s, ExecutionPlan([_slice()]))[0]["status"] == "submitted"
    s._http.post = AsyncMock(side_effect=ConnectionError("down"))
    assert _run(s, ExecutionPlan([_slice()]))[0]["status"] == "error"


# ------------------------------------------------------------------ the ledger rows

def _rows(s):
    return s._execution_log.recent(limit=100)[::-1]


def test_a_submitted_slice_is_recorded_with_what_a_parity_check_needs(tmp_path):
    s = _sched(tmp_path)
    s._current_cycle_id = "cycle_7"
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted", "order_id": "o-123", "broker_status": "accepted"}))
    _run(s, ExecutionPlan([_slice("buy", reduce_only=False)]))
    (row,) = _rows(s)
    assert (row["cycle_id"], row["symbol"], row["side"], row["qty"]) == ("cycle_7", "AAPL", "buy", 10.0)
    assert row["outcome"] == "submitted" and row["order_id"] == "o-123" and row["broker_status"] == "accepted"
    assert row["reference_price"] == 187.2 and row["spread_bps"] == 3.1
    assert row["order_type"] == "market" and row["client_order_id"].startswith("sched-AAPL-buy-") and row["http_status"] == 200
    assert row["reduce_only"] == 0 and row["recorded_at"]


def test_a_rejected_and_an_errored_slice_are_recorded_with_their_reason(tmp_path):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(side_effect=[
        _resp(200, {"status": "rejected", "reason": "kill switch", "reason_code": "halted"}),
        ConnectionError("down"),
    ])
    _run(s, ExecutionPlan([_slice(n=1, total=2), _slice(n=2, total=2)]))
    rej, err = _rows(s)
    assert rej["outcome"] == "rejected" and "kill switch" in rej["reason"]
    assert err["outcome"] == "error" and "down" in err["reason"]


def test_a_gate_skipped_slice_is_recorded_with_why(tmp_path):
    s = _sched(tmp_path)

    async def _get(url, params=None, **kw):
        return _resp(200, {"ok": True, "spread_bps": 500.0}) if "/stock/quote" in url else _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock()
    _run(s, ExecutionPlan([_slice()]))
    (row,) = _rows(s)
    assert row["outcome"] == "skipped" and row["spread_bps"] == 500.0 and row["reason"] and row["order_id"] is None
    s._http.post.assert_not_called()


def test_a_reducing_slice_is_flagged_reduce_only_in_the_ledger(tmp_path):
    s = _sched(tmp_path, scheduler_exits_exempt_from_halts=True)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted"}))
    _run(s, ExecutionPlan([_slice("sell", reduce_only=True)]))
    assert _rows(s)[0]["reduce_only"] == 1


def test_a_missing_reference_price_is_stored_as_null_not_invented(tmp_path):
    s = _sched(tmp_path)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted"}))
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        asyncio.run(s._execute_plan(ExecutionPlan([_slice()]), {}))
    assert _rows(s)[0]["reference_price"] is None


# ------------------------------------------------------------------ the ledger never gets in the way

def test_disabled_creates_no_file_and_orders_still_go(tmp_path):
    s = _sched(tmp_path, execution_log_enabled=False)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted"}))
    (out,) = _run(s, ExecutionPlan([_slice()]))
    assert out["status"] == "submitted" and s._execution_log is None
    assert not (tmp_path / "execution_log.db").exists()


def test_a_broken_ledger_never_stops_an_order(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.record = MagicMock(side_effect=RuntimeError("disk full"))
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted"}))
    (out,) = _run(s, ExecutionPlan([_slice()]))
    assert out["status"] == "submitted" and s._http.post.await_count == 1


def test_the_ledger_swallows_its_own_write_errors(tmp_path):
    log = ExecutionLog(tmp_path / "x.db")
    log.record(symbol="AAPL", side="buy", qty=1.0, outcome="submitted")
    log.record(symbol=None, side="buy", qty=1.0, outcome="submitted")        # NOT NULL violation: swallowed
    log.record(bogus_key=1, symbol="MSFT", side="buy", qty=1.0, outcome="skipped")   # unknown key ignored
    assert [r["symbol"] for r in log.recent()] == ["MSFT", "AAPL"]


def test_summary_counts_outcomes_and_coverage(tmp_path):
    log = ExecutionLog(tmp_path / "x.db")
    log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", reference_price=10.0, spread_bps=2.0)
    log.record(symbol="B", side="buy", qty=1.0, outcome="rejected", reference_price=None)
    sm = log.summary()
    assert (sm["total"], sm["by_outcome"], sm["with_reference_price"], sm["with_spread"]) == (2, {"submitted": 1, "rejected": 1}, 1, 1)
    assert (sm["filled"], sm["with_slippage"], sm["mean_slippage_bps"], sm["median_slippage_bps"]) == (0, 0, None, None)
    assert [r["symbol"] for r in log.recent(symbol="a")] == ["A"]


def test_whole_cycle_reports_a_refused_order_as_refused(tmp_path):
    s = _sched(tmp_path, twap_slices=1)

    async def _get(url, params=None, **kw):
        if "/portfolio/state" in url:
            return _resp(200, {"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
        if "/broker/positions" in url:
            return _resp(200, [])
        if "/broker/account" in url:
            return _resp(200, {"configured": False})
        if "/candles/" in url:
            return _resp(200, {"data": [{"close": 100.0, "bar_ts": 1_700_000_000}]})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "rejected", "reason": "kill switch"}))
    s._check_breaker = AsyncMock(return_value=("ALLOW", None))
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        r = asyncio.run(s.cycle())
    assert r["submitted"][0]["status"] == "rejected"
    assert s._execution_log.summary()["by_outcome"] == {"rejected": 1}


# ------------------------------------------------------------------ the route

def test_route_reports_none_before_any_order(tmp_path):
    with patch("vinu_live.server.app.load_config", return_value=LiveConfig(data_root=tmp_path)):
        body = TestClient(create_app()).get("/live/executions").json()
    assert body["status"] == "none" and body["executions"] == []


def test_route_lists_rows_newest_first_with_a_summary_and_a_symbol_filter(tmp_path):
    log = ExecutionLog(tmp_path / "execution_log.db")
    log.record(symbol="AAPL", side="buy", qty=1.0, outcome="submitted", reference_price=1.0)
    log.record(symbol="MSFT", side="sell", qty=2.0, outcome="rejected", reason="x")
    log.close()
    with patch("vinu_live.server.app.load_config", return_value=LiveConfig(data_root=tmp_path)):
        client = TestClient(create_app())
        body = client.get("/live/executions").json()
        assert body["status"] == "ok" and [r["symbol"] for r in body["executions"]] == ["MSFT", "AAPL"]
        assert body["summary"]["by_outcome"] == {"submitted": 1, "rejected": 1}
        assert [r["symbol"] for r in client.get("/live/executions?symbol=aapl").json()["executions"]] == ["AAPL"]
        assert len(client.get("/live/executions?limit=1").json()["executions"]) == 1


def test_flag_defaults_on_and_reads_env(monkeypatch):
    assert LiveConfig().execution_log_enabled is True
    monkeypatch.setenv("VINU_LIVE_EXECUTION_LOG_ENABLED", "false")
    assert LiveConfig.from_env().execution_log_enabled is False
