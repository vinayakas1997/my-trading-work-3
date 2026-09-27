"""Tests for item #24 finding #1's fix: LiveScheduler.cycle() must call
check_limits() before planning/executing any order, not just log-and-
proceed. Mocks check_limits() itself (its own correctness is
test_breaker.py's job) to verify the WIRING: does the scheduler actually
call it, and does it actually skip execution on HALT.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_live.breaker.engine import BreakerVerdict
from vinu_live.config import LiveConfig
from vinu_live.scheduler import LiveScheduler


def _make_scheduler(tmp_path, **config_overrides) -> LiveScheduler:
    config = LiveConfig(data_root=tmp_path, **config_overrides)
    scheduler = LiveScheduler(config)
    scheduler._http = MagicMock()
    return scheduler


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    return resp


class TestCheckBreakerWiring:
    def test_cycle_calls_check_breaker_and_skips_execution_on_halt(self, tmp_path) -> None:
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
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch(
            "vinu_live.scheduler.check_limits",
            return_value=(BreakerVerdict.HALT, "daily_loss_breach"),
        ) as mock_check:
            result = asyncio.run(scheduler.cycle())

        assert mock_check.called
        assert result["status"] == "halted_by_breaker"
        assert result["breaker_reason"] == "daily_loss_breach"
        # No execution-plan/submission fields should be populated.
        assert "n_slices" not in result
        assert "submitted" not in result

    def test_cycle_executes_normally_when_breaker_allows(self, tmp_path) -> None:
        # twap_slices=1 -> schedule_slice_delays returns [] -> no real
        # asyncio.sleep() between slices (default twap_slices=6 over a
        # 60-minute window means real ~10-minute waits between slices,
        # which is correct production behavior but wrong for a test that
        # doesn't mock time).
        scheduler = _make_scheduler(tmp_path, twap_slices=1)

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

        async def _post(url, **kwargs):
            if "/agent/broker/order" in url:
                return _resp(status_code=200)
            raise AssertionError(f"unexpected POST: {url}")

        scheduler._http.get = AsyncMock(side_effect=_get)
        scheduler._http.post = AsyncMock(side_effect=_post)

        with patch(
            "vinu_live.scheduler.check_limits",
            return_value=(BreakerVerdict.ALLOW, None),
        ) as mock_check:
            result = asyncio.run(scheduler.cycle())

        assert mock_check.called
        assert result["status"] == "ok"
        assert "n_slices" in result

    def test_fresh_halt_engages_the_real_cross_process_kill_switch(self, tmp_path) -> None:
        """The whole point of the fix -- other processes (OrderGuard,
        the orchestrator) only ever see a HALT via the real kill switch,
        not this process's own in-memory BreakerState."""
        scheduler = _make_scheduler(tmp_path)
        assert scheduler._breaker_state.halted is False

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
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch(
            "vinu_live.scheduler.check_limits",
            return_value=(BreakerVerdict.HALT, "leverage_breach"),
        ):
            asyncio.run(scheduler.cycle())

        halt_calls = [
            c for c in scheduler._http.post.call_args_list
            if "/agent/broker/halt" in c.args[0]
        ]
        assert len(halt_calls) == 1
        assert halt_calls[0].kwargs["json"]["reason"] == "breaker: leverage_breach"

    def test_already_halted_does_not_re_engage_the_kill_switch_every_cycle(self, tmp_path) -> None:
        scheduler = _make_scheduler(tmp_path)
        scheduler._breaker_state.halted = True  # already halted from a prior cycle

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
        scheduler._http.post = AsyncMock(return_value=_resp(status_code=200))

        with patch(
            "vinu_live.scheduler.check_limits",
            return_value=(BreakerVerdict.HALT, "still halted"),
        ):
            asyncio.run(scheduler.cycle())

        halt_calls = [
            c for c in scheduler._http.post.call_args_list
            if "/agent/broker/halt" in c.args[0]
        ]
        assert len(halt_calls) == 0
