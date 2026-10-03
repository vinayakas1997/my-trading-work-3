"""Fill enrichment for the scheduler's order ledger: ask the broker how recently accepted orders ended up, and
write fill price / quantity / status and the slippage against the decision-time quote mid.

Slippage is positive when the fill was WORSE than the reference (a buy above it, a sell below it). Reference =
the quote mid recorded at decision time, else the sizing reference price (the last daily close, which also holds
any overnight gap; `slippage_ref` says which).
"""

from __future__ import annotations

import asyncio
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.config import LiveConfig
from vinu_live.execution import ExecutionPlan, ExecutionSlice
from vinu_live.execution_log import ExecutionLog
from vinu_live.scheduler import LiveScheduler
from vinu_live.trade_plan.guards import fetch_quote_snapshot


def _resp(status=200, body=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


# ------------------------------------------------------------------ quote snapshot

def _http_with(payload, status=200, raises=None):
    http = MagicMock()
    if raises:
        http.get = AsyncMock(side_effect=raises)
    else:
        http.get = AsyncMock(return_value=_resp(status, payload))
    return http


def test_quote_snapshot_returns_spread_and_mid():
    out = asyncio.run(fetch_quote_snapshot(_http_with({"ok": True, "spread_bps": 3.2, "mid": 187.4}), "http://x", "AAPL"))
    assert out == (3.2, 187.4)


@pytest.mark.parametrize("payload,status,spread", [
    ({"ok": False, "mid": 5.0}, 200, None),                      # not ok: neither field is trusted
    ({"ok": True, "spread_bps": 2.0, "mid": None}, 200, 2.0),    # spread alone survives a missing mid
    ({"ok": True, "spread_bps": 2.0, "mid": -1}, 200, 2.0),
    ({"ok": True, "spread_bps": 2.0, "mid": "x"}, 200, 2.0),
    (None, 500, None),
    ("junk", 200, None),
])
def test_quote_snapshot_fails_open_per_field(payload, status, spread):
    got_spread, mid = asyncio.run(fetch_quote_snapshot(_http_with(payload, status), "http://x", "AAPL"))
    assert mid is None and got_spread == spread


def test_quote_snapshot_swallows_a_connection_error():
    assert asyncio.run(fetch_quote_snapshot(_http_with(None, raises=ConnectionError("x")), "http://x", "AAPL")) == (None, None)


# ------------------------------------------------------------------ ledger: migration, unresolved, record_fill

def _log(tmp_path):
    return ExecutionLog(tmp_path / "x.db")


def test_a_fresh_ledger_has_the_fill_columns(tmp_path):
    log = _log(tmp_path)
    log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", quote_mid=10.0)
    row = log.recent()[0]
    for col in ("quote_mid", "fill_price", "filled_qty", "fill_status", "fill_checked_at", "slippage_bps", "slippage_ref"):
        assert col in row
    assert row["quote_mid"] == 10.0 and row["fill_price"] is None


def test_a_version_one_ledger_is_migrated_in_place(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(ExecutionLog.SCHEMA)
    conn.execute("INSERT INTO scheduler_executions (recorded_at, symbol, side, qty, outcome) VALUES ('2026-01-01', 'OLD', 'buy', 1, 'submitted')")
    conn.commit()
    conn.close()
    log = ExecutionLog(path)
    (row,) = log.recent()
    assert row["symbol"] == "OLD" and "slippage_bps" in row


@pytest.mark.parametrize("side,fill,expected", [
    ("buy", 100.10, 10.0), ("buy", 99.90, -10.0), ("sell", 99.90, 10.0), ("sell", 100.10, -10.0), ("buy", 100.0, 0.0),
])
def test_slippage_is_positive_when_the_fill_is_worse_and_uses_the_quote_mid(tmp_path, side, fill, expected):
    log = _log(tmp_path)
    log.record(symbol="A", side=side, qty=1.0, outcome="submitted", order_id="o", quote_mid=100.0, reference_price=90.0)
    row_id = log.recent()[0]["id"]
    slip = log.record_fill(row_id, fill_status="filled", fill_price=fill, filled_qty=1.0)
    assert slip == pytest.approx(expected)
    row = log.recent()[0]
    assert row["slippage_ref"] == "mid" and row["fill_status"] == "filled" and row["fill_price"] == fill and row["fill_checked_at"]


def test_slippage_falls_back_to_the_daily_close_and_says_so(tmp_path):
    log = _log(tmp_path)
    log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", order_id="o", reference_price=100.0)
    log.record_fill(log.recent()[0]["id"], fill_status="filled", fill_price=101.0, filled_qty=1.0)
    row = log.recent()[0]
    assert row["slippage_bps"] == pytest.approx(100.0) and row["slippage_ref"] == "close"


def test_no_fill_price_or_no_reference_means_no_slippage_not_a_made_up_one(tmp_path):
    log = _log(tmp_path)
    log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", order_id="o1", quote_mid=100.0)
    log.record(symbol="B", side="buy", qty=1.0, outcome="submitted", order_id="o2")
    a, b = sorted(log.recent(), key=lambda r: r["symbol"])
    assert log.record_fill(a["id"], fill_status="accepted", fill_price=None, filled_qty=0.0) is None
    assert log.record_fill(b["id"], fill_status="filled", fill_price=50.0, filled_qty=1.0) is None
    assert all(r["slippage_bps"] is None for r in log.recent())


def test_unresolved_orders_skip_final_unaccepted_old_and_idless_rows(tmp_path):
    log = _log(tmp_path)
    log.record(symbol="OPEN", side="buy", qty=1.0, outcome="submitted", order_id="o1")
    log.record(symbol="DONE", side="buy", qty=1.0, outcome="submitted", order_id="o2")
    log.record(symbol="PART", side="buy", qty=1.0, outcome="submitted", order_id="o3")
    log.record(symbol="REJ", side="buy", qty=1.0, outcome="rejected", order_id="o4")
    log.record(symbol="NOID", side="buy", qty=1.0, outcome="submitted")
    by_sym = {r["symbol"]: r["id"] for r in log.recent()}
    log.record_fill(by_sym["DONE"], fill_status="filled", fill_price=1.0, filled_qty=1.0)
    log.record_fill(by_sym["PART"], fill_status="partially_filled", fill_price=1.0, filled_qty=0.5)
    assert {r["symbol"] for r in log.unresolved_orders()} == {"OPEN", "PART"}      # a partial fill is still being watched
    assert log.unresolved_orders(max_age_days=-1) == []                              # everything is "too old"
    assert len(log.unresolved_orders(limit=1)) == 1


def test_summary_reports_fills_and_slippage(tmp_path):
    log = _log(tmp_path)
    for i, fill in enumerate([100.1, 100.3, 99.9]):
        log.record(symbol=f"S{i}", side="buy", qty=1.0, outcome="submitted", order_id=f"o{i}", quote_mid=100.0)
    for r in log.recent():
        px = {"S0": 100.1, "S1": 100.3, "S2": 99.9}[r["symbol"]]
        log.record_fill(r["id"], fill_status="filled", fill_price=px, filled_qty=1.0)
    sm = log.summary()
    assert sm["filled"] == 3 and sm["with_slippage"] == 3
    assert sm["mean_slippage_bps"] == pytest.approx((10 + 30 - 10) / 3) and sm["median_slippage_bps"] == pytest.approx(10.0)


# ------------------------------------------------------------------ the scheduler pass

def _sched(tmp_path, **cfg):
    s = LiveScheduler(LiveConfig(data_root=tmp_path, **cfg))
    s._http = MagicMock()
    return s


def test_the_pass_writes_fills_for_unresolved_orders_and_leaves_resolved_ones(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.record(symbol="AAPL", side="buy", qty=5.0, outcome="submitted", order_id="ord-1", quote_mid=100.0)
    s._execution_log.record(symbol="MSFT", side="sell", qty=5.0, outcome="submitted", order_id="ord-2", quote_mid=200.0)
    asked: list[str] = []

    async def _get(url, **kw):
        asked.append(url.rsplit("/", 1)[1])
        oid = url.rsplit("/", 1)[1]
        return _resp(200, {"status": "ok", "order_status": "filled", "filled_qty": 5.0,
                           "filled_avg_price": 100.2 if oid == "ord-1" else 199.8})

    s._http.get = AsyncMock(side_effect=_get)
    asyncio.run(s._enrich_execution_fills())
    rows = {r["symbol"]: r for r in s._execution_log.recent()}
    assert rows["AAPL"]["slippage_bps"] == pytest.approx(20.0) and rows["MSFT"]["slippage_bps"] == pytest.approx(10.0)
    asyncio.run(s._enrich_execution_fills())
    assert sorted(asked) == ["ord-1", "ord-2"]            # second pass: both are final, nothing asked again


def test_a_partial_fill_is_recorded_and_asked_about_again(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.record(symbol="AAPL", side="buy", qty=10.0, outcome="submitted", order_id="o", quote_mid=100.0)
    s._http.get = AsyncMock(return_value=_resp(200, {"status": "ok", "order_status": "partially_filled", "filled_qty": 4.0, "filled_avg_price": 100.1}))
    asyncio.run(s._enrich_execution_fills())
    row = s._execution_log.recent()[0]
    assert row["fill_status"] == "partially_filled" and row["filled_qty"] == 4.0
    asyncio.run(s._enrich_execution_fills())
    assert s._http.get.await_count == 2


@pytest.mark.parametrize("answer", [
    _resp(200, {"status": "error", "error": "alpaca down"}), _resp(200, {"status": "unconfigured"}), _resp(503), _resp(200, ["junk"]),
])
def test_unusable_answers_leave_the_row_for_the_next_cycle(tmp_path, answer):
    s = _sched(tmp_path)
    s._execution_log.record(symbol="AAPL", side="buy", qty=1.0, outcome="submitted", order_id="o", quote_mid=100.0)
    s._http.get = AsyncMock(return_value=answer)
    asyncio.run(s._enrich_execution_fills())
    assert s._execution_log.recent()[0]["fill_status"] is None and len(s._execution_log.unresolved_orders()) == 1


def test_one_failing_lookup_does_not_stop_the_others(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", order_id="bad", quote_mid=100.0)
    s._execution_log.record(symbol="B", side="buy", qty=1.0, outcome="submitted", order_id="good", quote_mid=100.0)

    async def _get(url, **kw):
        if url.endswith("/bad"):
            raise ConnectionError("down")
        return _resp(200, {"status": "ok", "order_status": "filled", "filled_qty": 1.0, "filled_avg_price": 100.0})

    s._http.get = AsyncMock(side_effect=_get)
    asyncio.run(s._enrich_execution_fills())
    rows = {r["symbol"]: r for r in s._execution_log.recent()}
    assert rows["B"]["fill_status"] == "filled" and rows["A"]["fill_status"] is None


def test_the_batch_size_bounds_the_lookups(tmp_path):
    s = _sched(tmp_path, execution_fill_enrichment_batch=2)
    for i in range(5):
        s._execution_log.record(symbol=f"S{i}", side="buy", qty=1.0, outcome="submitted", order_id=f"o{i}", quote_mid=100.0)
    s._http.get = AsyncMock(return_value=_resp(200, {"status": "ok", "order_status": "filled", "filled_qty": 1.0, "filled_avg_price": 100.0}))
    asyncio.run(s._enrich_execution_fills())
    assert s._http.get.await_count == 2


def test_disabled_or_no_ledger_asks_nothing(tmp_path):
    s = _sched(tmp_path, execution_fill_enrichment_enabled=False)
    s._execution_log.record(symbol="A", side="buy", qty=1.0, outcome="submitted", order_id="o")
    s._http.get = AsyncMock()
    asyncio.run(s._enrich_execution_fills())
    s2 = _sched(tmp_path / "n", execution_log_enabled=False)
    s2._http.get = AsyncMock()
    asyncio.run(s2._enrich_execution_fills())
    s._http.get.assert_not_called()
    s2._http.get.assert_not_called()


def test_a_broken_ledger_never_breaks_the_pass(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.unresolved_orders = MagicMock(side_effect=RuntimeError("disk"))
    asyncio.run(s._enrich_execution_fills())          # does not raise


def test_a_cycle_runs_the_pass_first_and_a_slice_records_the_quote_mid(tmp_path):
    s = _sched(tmp_path)
    s._execution_log.record(symbol="OLD", side="buy", qty=1.0, outcome="submitted", order_id="old-1", quote_mid=100.0)

    async def _get(url, params=None, **kw):
        if "/broker/order/" in url:
            return _resp(200, {"status": "ok", "order_status": "filled", "filled_qty": 1.0, "filled_avg_price": 100.5})
        if "/stock/quote" in url:
            return _resp(200, {"ok": True, "spread_bps": 2.0, "mid": 187.3})
        return _resp(404)

    s._http.get = AsyncMock(side_effect=_get)
    s._http.post = AsyncMock(return_value=_resp(200, {"status": "submitted", "order_id": "new-1"}))
    with patch("vinu_live.scheduler.asyncio.sleep", AsyncMock()), patch("vinu_live.scheduler.halt_reason", AsyncMock(return_value=None)):
        asyncio.run(s._execute_plan(
            ExecutionPlan([ExecutionSlice(symbol="AAPL", side="buy", qty=10.0, slice_number=1, total_slices=1)]), {"AAPL": 187.0}))
        s._current_cycle_id = ""
        asyncio.run(s._enrich_execution_fills())
    rows = {r["symbol"]: r for r in s._execution_log.recent()}
    assert rows["AAPL"]["quote_mid"] == 187.3 and rows["AAPL"]["order_id"] == "new-1"
    assert rows["OLD"]["slippage_bps"] == pytest.approx(50.0)


def test_flags_default_on_and_read_env(monkeypatch):
    c = LiveConfig()
    assert c.execution_fill_enrichment_enabled is True and c.execution_fill_enrichment_batch == 25
    monkeypatch.setenv("VINU_LIVE_EXECUTION_FILL_ENRICHMENT_ENABLED", "false")
    monkeypatch.setenv("VINU_LIVE_EXECUTION_FILL_ENRICHMENT_BATCH", "5")
    c = LiveConfig.from_env()
    assert c.execution_fill_enrichment_enabled is False and c.execution_fill_enrichment_batch == 5
