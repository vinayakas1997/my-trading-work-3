"""Tests for point 7 option 1 (reverse-engineering/
06-execution-handoff-and-architecture.md): LiveScheduler.cycle() must
fold unapplied live_decision EXECUTE verdicts into the same
target_weights flow the normal portfolio-rebalance weights go through,
sized by each strategy's own live_decision_position_size config field.
Mocks check_limits() (its own correctness is test_breaker.py's job) so
these tests are pure ALLOW-path wiring checks.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.live_decision.schema import LiveDecisionRecord
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    list_open_positions,
    list_unapplied_executes,
    record_live_decision,
)
from vinu_live.scheduler import LiveScheduler


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


def _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross") -> None:
    backend = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
    try:
        record_live_decision(backend, LiveDecisionRecord(
            ticker=ticker, strategy_id=strategy_id, trigger_id="trig_1", bar_ts=1000,
            decision="EXECUTE", precondition_held=True,
            reasoning="real evidence cited", raw_content="full content",
        ))
    finally:
        backend.close()


class TestLiveDecisionWeightsMerge:
    def test_sized_execute_produces_a_real_order_and_is_marked_applied(self, tmp_path) -> None:
        _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross")
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/strategy/strategies/sma_cross" in url:
                return _resp(json_body={"name": "sma_cross", "live_decision_position_size": 0.05})
            if "/agent/broker/positions" in url:
                return _resp(json_body=[])
            if "/agent/broker/account" in url:
                return _resp(json_body={"configured": False})
            if "/candles/" in url:
                return _resp(json_body={"data": [{"close": 150.0}]})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
            result = asyncio.run(scheduler.cycle())

        assert result["status"] == "ok"
        assert result.get("n_instructions") == 1
        assert result.get("submitted")
        assert result["submitted"][0]["symbol"] == "AAPL"

        # The decision must be consumed -- not re-applied every cycle.
        assert list_unapplied_executes(scheduler._live_decision_backend) == []
        # But it must now have become a real, still-open position -- the
        # exit-mechanism fix's whole point.
        open_positions = list_open_positions(scheduler._live_decision_backend)
        assert len(open_positions) == 1
        assert open_positions[0].ticker == "AAPL"
        assert open_positions[0].position_size == 0.05

    def test_unsized_execute_produces_no_order_but_is_still_marked_applied(self, tmp_path) -> None:
        """No live_decision_position_size configured is real, final
        information (the strategy author hasn't wired sizing yet), not a
        transient failure -- it must not be re-logged/re-checked forever."""
        _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross")
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/strategy/strategies/sma_cross" in url:
                return _resp(json_body={"name": "sma_cross"})  # no live_decision_position_size
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)

        result = asyncio.run(scheduler.cycle())

        assert result["status"] == "skipped_no_weights"
        assert list_unapplied_executes(scheduler._live_decision_backend) == []

    def test_strategy_fetch_failure_leaves_the_decision_unapplied_to_retry(self, tmp_path) -> None:
        _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross")
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/strategy/strategies/sma_cross" in url:
                return _resp(status_code=500)
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)

        result = asyncio.run(scheduler.cycle())

        assert result["status"] == "skipped_no_weights"
        pending = list_unapplied_executes(scheduler._live_decision_backend)
        assert len(pending) == 1
        assert pending[0].ticker == "AAPL"

    def test_no_pending_decisions_means_no_strategy_api_call_at_all(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)

        result = asyncio.run(scheduler.cycle())
        assert result["status"] == "skipped_no_weights"

    def test_live_decision_weight_still_goes_through_the_breaker_check(self, tmp_path) -> None:
        """The whole point of routing through the existing target_weights
        path -- point 7's risk-limit fix applies here too, for free."""
        _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross")
        scheduler = _make_scheduler(tmp_path)

        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/strategy/strategies/sma_cross" in url:
                return _resp(json_body={"name": "sma_cross", "live_decision_position_size": 0.05})
            if "/agent/broker/positions" in url:
                return _resp(json_body=[])
            if "/agent/broker/account" in url:
                return _resp(json_body={"configured": False})
            if "/candles/" in url:
                return _resp(json_body={"data": [{"close": 150.0}]})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch(
            "vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.HALT, "daily_loss_breach"),
        ) as mock_check:
            result = asyncio.run(scheduler.cycle())

        assert mock_check.called
        assert result["status"] == "halted_by_breaker"
        assert "submitted" not in result


class TestOpenPositionReEmittedEveryCycle:
    """The exit-mechanism fix itself (missing-pieces-of-system/new-theory-
    of-trading/system-wide-audit-and-design/
    04-synthesis-built-vs-missing-2026-09-28.md): previously an EXECUTE
    was folded into target_weights for exactly one cycle, then never
    again -- since SignalTranslator treats a held-but-untargeted symbol as
    target 0.0, that force-closed the position the very next cycle. This
    proves the fix: a position already open (no new unapplied EXECUTE
    this cycle) still gets a real target_weights entry."""

    def test_second_cycle_still_emits_the_open_positions_weight(self, tmp_path) -> None:
        _record_execute(tmp_path, ticker="AAPL", strategy_id="sma_cross")
        scheduler = _make_scheduler(tmp_path)

        # Real configured equity, held fixed across both cycles -- avoids
        # entangling this test with the unconfigured-account fallback's
        # own circular "value the portfolio from what it currently holds"
        # behavior, which is unrelated to what this test is proving.
        async def _get(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/strategy/strategies/sma_cross" in url:
                return _resp(json_body={"name": "sma_cross", "live_decision_position_size": 0.05})
            if "/agent/broker/positions" in url:
                return _resp(json_body=[])
            if "/agent/broker/account" in url:
                return _resp(json_body={"configured": True, "equity": 1_000_000.0})
            if "/candles/" in url:
                return _resp(json_body={"data": [{"close": 150.0}]})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
            first = asyncio.run(scheduler.cycle())
        assert first["submitted"][0]["symbol"] == "AAPL"
        opened_qty = first["submitted"][0]["qty"]

        # No new EXECUTE this cycle -- list_unapplied_executes() is now
        # empty -- but the position from cycle 1 is still open and must
        # still produce a target_weights entry, or the broker's real
        # AAPL holding (now present, unlike cycle 1's empty positions)
        # would get force-closed by SignalTranslator's own "not targeted
        # -> close" rule.
        async def _get_cycle_2(url, **kwargs):
            if "/portfolio/state" in url:
                return _resp(json_body={"status": "empty", "weights": []})
            if "/agent/broker/positions" in url:
                return _resp(json_body=[{"symbol": "AAPL", "qty": opened_qty}])
            if "/agent/broker/account" in url:
                return _resp(json_body={"configured": True, "equity": 1_000_000.0})
            if "/candles/" in url:
                return _resp(json_body={"data": [{"close": 150.0}]})
            raise AssertionError(f"unexpected GET: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get_cycle_2)

        with patch("vinu_live.scheduler.check_limits", return_value=(BreakerVerdict.ALLOW, None)):
            second = asyncio.run(scheduler.cycle())

        # No close instruction for AAPL -- the position's weight was
        # re-emitted, so the diff against the still-held qty is ~zero.
        assert second.get("n_instructions", 0) == 0
        assert "submitted" not in second or second["submitted"] == []
