"""Tests for item #24 finding #3's fix: LiveScheduler.cycle() built a
ReconciliationReport but nothing ever inspected it or notified on real
drift. Deliberately NOT "notify on any single cycle's drift" -- this
reconciliation compares a just-changed target against positions fetched
before this same cycle's own orders were submitted, so one cycle of
drift is the expected gap those orders are already closing. Only a
streak of RECON_DRIFT_ALERT_CYCLES consecutive cycles is alert-worthy,
edge-triggered so it notifies once per newly-persistent streak, same
shape as orchestrator.py's own book-vs-broker drift notify.

`_handle_reconciliation_drift` is tested directly against constructed
`ReconciliationReport`s (same "test the wiring, not re-derive full
system dynamics" posture test_scheduler_breaker.py already uses for
check_limits) -- full multi-cycle arithmetic through `cycle()` would
mean re-deriving `_fetch_portfolio_value`'s own fallback-vs-priced-
positions branching for every scenario, which is a different unit's job.
One end-to-end test confirms `cycle()` actually calls this method at all.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.reconciliation import ReconciliationReport
from vinu_live.scheduler import RECON_DRIFT_ALERT_CYCLES, LiveScheduler


def _make_scheduler(tmp_path, **config_overrides) -> LiveScheduler:
    config = LiveConfig(data_root=tmp_path, twap_slices=1, **config_overrides)
    scheduler = LiveScheduler(config)
    scheduler._http = MagicMock()
    return scheduler


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


def _drifting_report(symbol="AAPL", expected=100.0, actual=40.0) -> ReconciliationReport:
    return ReconciliationReport(
        drift_detected=True,
        symbol_drifts=[{
            "symbol": symbol, "expected_qty": expected, "actual_qty": actual,
            "diff": actual - expected, "drift_pct": 60.0,
        }],
        total_drift_pct=60.0,
    )


def _clean_report() -> ReconciliationReport:
    return ReconciliationReport()


class TestHandleReconciliationDrift:
    def test_a_single_cycles_drift_does_not_notify(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.post = AsyncMock(return_value=_resp())

        asyncio.run(scheduler._handle_reconciliation_drift(_drifting_report()))

        scheduler._http.post.assert_not_called()
        assert scheduler._recon_drift_streak == {"AAPL": 1}

    def test_a_persistent_streak_notifies_exactly_once(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.post = AsyncMock(return_value=_resp())

        async def _run():
            for _ in range(RECON_DRIFT_ALERT_CYCLES + 2):
                await scheduler._handle_reconciliation_drift(_drifting_report())

        asyncio.run(_run())

        assert scheduler._http.post.call_count == 1
        call = scheduler._http.post.call_args
        assert "/notify/reconciliation-drift" in call.args[0]
        payload = call.kwargs["json"]
        assert payload == {
            "symbol": "AAPL", "action": "target_weight_drift",
            "expected_qty": 100.0, "actual_qty": 40.0, "drift_pct": 60.0,
        }

    def test_drift_clearing_resets_the_streak_so_it_can_notify_again_later(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.post = AsyncMock(return_value=_resp())

        async def _run():
            for _ in range(RECON_DRIFT_ALERT_CYCLES):
                await scheduler._handle_reconciliation_drift(_drifting_report())
            # position fills -- no drift this cycle
            await scheduler._handle_reconciliation_drift(_clean_report())
            # drift recurs -- must notify again (a fresh occurrence, not
            # suppressed forever by the earlier notification)
            for _ in range(RECON_DRIFT_ALERT_CYCLES):
                await scheduler._handle_reconciliation_drift(_drifting_report())

        asyncio.run(_run())

        assert scheduler._http.post.call_count == 2

    def test_independent_symbols_track_independent_streaks(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.post = AsyncMock(return_value=_resp())

        async def _run():
            for _ in range(RECON_DRIFT_ALERT_CYCLES):
                await scheduler._handle_reconciliation_drift(_drifting_report(symbol="AAPL"))
            # MSFT only just started drifting -- must not inherit AAPL's streak
            await scheduler._handle_reconciliation_drift(_drifting_report(symbol="MSFT"))

        asyncio.run(_run())

        assert scheduler._http.post.call_count == 1
        assert scheduler._http.post.call_args.kwargs["json"]["symbol"] == "AAPL"
        assert scheduler._recon_drift_streak["MSFT"] == 1

    def test_notify_failure_does_not_raise(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._http.post = AsyncMock(side_effect=ConnectionError("notify down"))

        async def _run():
            for _ in range(RECON_DRIFT_ALERT_CYCLES):
                await scheduler._handle_reconciliation_drift(_drifting_report())

        asyncio.run(_run())  # must not raise


class TestCycleWiresReconciliationDrift:
    """One end-to-end check that `cycle()` actually calls the method
    above at all -- the real gap item #24 finding #3 described
    (`cli.py::worker_main` never inspected the recon report)."""

    def test_cycle_feeds_its_own_recon_report_through(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"weights": [{"symbol": "AAPL", "target_weight": 0.1}]})
            if "/agent/broker/positions" in url:
                return _resp(json_body=[])
            if "/agent/broker/account" in url:
                return _resp(json_body={"configured": False})
            if "/candles/" in url:
                return _resp(json_body={"data": [{"close": 150.0}]})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp())

        with patch(
            "vinu_live.scheduler.LiveScheduler._handle_reconciliation_drift",
            new_callable=AsyncMock,
        ) as mock_handle, patch(
            "vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None),
        ):
            asyncio.run(scheduler.cycle())

        mock_handle.assert_awaited_once()
        report = mock_handle.await_args.args[0]
        assert report.drift_detected is True  # {} current vs. a real nonzero target
