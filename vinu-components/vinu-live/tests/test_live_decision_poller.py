import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest

from vinu_live.config import LiveConfig
from vinu_live.live_decision.poller import CandleClosePoller, timeframe_to_seconds
from vinu_live.live_decision.storage import LiveDecisionBackend, get_cursor, list_transitions


def _resp(status_code=200, json_body=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


def _bars(n: int, start_ts: int = 1_700_000_000, step: int = 900):
    return {
        "count": n,
        "data": [
            {
                "open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i,
                "close": 100.5 + i, "volume": 1000.0, "ts": start_ts + i * step,
            }
            for i in range(n)
        ],
    }


@pytest.fixture
def poller():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    backend = LiveDecisionBackend(db_path)
    config = LiveConfig()
    p = CandleClosePoller(config, backend=backend)
    p._http = MagicMock()
    yield p
    backend.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_timeframe_to_seconds_known_values():
    assert timeframe_to_seconds("15m") == 900
    assert timeframe_to_seconds("1h") == 3600
    assert timeframe_to_seconds("1d") == 86400


def test_timeframe_to_seconds_unknown_defaults_to_daily():
    assert timeframe_to_seconds("weird") == 86400


def test_cycle_groups_shared_ticker_timeframe_into_one_fetch(poller):
    """Two strategies both watching AAPL on 15m -- must produce exactly
    one bars-fetch group, not two, per the poller's own "one fetch per
    (ticker, timeframe), not one per strategy" design rule."""
    fetch_count = {"n": 0}

    async def _get(url, params=None, **kwargs):
        if "/strategy/strategies/strat_a" in url:
            return _resp(json_body={
                "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                "must_conditions": [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 999}],
                "confirmation_conditions": [], "grace_window_bars": 5,
            })
        if "/strategy/strategies/strat_b" in url:
            return _resp(json_body={
                "name": "strat_b", "schedule": "15m", "universe": ["AAPL"],
                "must_conditions": [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 999}],
                "confirmation_conditions": [], "grace_window_bars": 5,
            })
        if "/strategy/strategies" in url:
            return _resp(json_body=[
                {"name": "strat_a", "enabled": True},
                {"name": "strat_b", "enabled": True},
            ])
        if "/stock/candles/AAPL" in url:
            fetch_count["n"] += 1
            limit = (params or {}).get("limit", 2)
            return _resp(json_body=_bars(min(limit, 260)))
        raise AssertionError(f"unexpected URL: {url}")

    poller._http.get = AsyncMock(side_effect=_get)

    result = asyncio.run(poller.cycle())

    assert result["ticker_timeframe_pairs"] == 1
    # 1 small "latest" fetch + 1 full warmup fetch = 2, regardless of how
    # many strategies share the (ticker, timeframe) pair.
    assert fetch_count["n"] == 2
    assert result["candle_close_events"] == 2  # both strategies still get evaluated


def test_cycle_skips_pair_when_no_newer_bar_than_cursor(poller):
    async def _get(url, params=None, **kwargs):
        if "/strategy/strategies/strat_a" in url:
            return _resp(json_body={
                "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
            })
        if "/strategy/strategies" in url:
            return _resp(json_body=[{"name": "strat_a", "enabled": True}])
        if "/stock/candles/AAPL" in url:
            return _resp(json_body=_bars(2, start_ts=1000))
        raise AssertionError(f"unexpected URL: {url}")

    poller._http.get = AsyncMock(side_effect=_get)
    # Pre-seed the cursor at-or-past the fetched bar's timestamp.
    from vinu_live.live_decision.storage import advance_cursor
    advance_cursor(poller._backend, "AAPL", "15m", 1000 + 900)  # matches _bars(2)'s last ts

    result = asyncio.run(poller.cycle())

    assert result["candle_close_events"] == 0


class TestLiveDecisionTrigger:
    """Point 5's trigger (reverse-engineering/
    06-execution-handoff-and-architecture.md, resolved): the poller must
    call vinu-agent's /agent/live-decision/run exactly once when a pair
    freshly reaches ready_to_execute -- not on every cycle it stays
    there, and must resolve the trigger's lifecycle (mark_executed) on
    a real decision.
    """

    def _strategies_resp(self, must_conditions):
        return {
            "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
            "must_conditions": must_conditions, "confirmation_conditions": [],
            "grace_window_bars": 5,
        }

    def test_fresh_ready_to_execute_triggers_the_agent_and_resolves_execute(self, poller):
        live_decision_calls = []

        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                live_decision_calls.append(json)
                return _resp(json_body={"status": "ok", "decision": "EXECUTE", "reasoning": "real evidence"})
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=_post)

        result = asyncio.run(poller.cycle())

        assert len(live_decision_calls) == 1
        assert live_decision_calls[0]["ticker"] == "AAPL"
        assert live_decision_calls[0]["strategy_id"] == "strat_a"

        from vinu_live.live_decision.storage import get_stage_state
        state = get_stage_state(poller._backend, "AAPL", "strat_a")
        assert state.stage == "executed"

    def test_still_waiting_in_grace_window_does_not_trigger(self, poller):
        """A must-condition alone (no confirmation) with a condition that
        never fires stays idle -- never reaches ready_to_execute, so no
        trigger call should happen at all."""
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 999999}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=AssertionError("should never POST"))

        asyncio.run(poller.cycle())  # must not raise from the AssertionError side_effect

    def test_a_real_decision_is_durably_recorded_not_just_logged(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                return _resp(json_body={
                    "status": "ok", "decision": "EXECUTE", "precondition_held": True,
                    "reasoning": "12 of 15 recorded triggers extended",
                    "content": "EXECUTE -- full reasoning...",
                })
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=_post)

        asyncio.run(poller.cycle())

        from vinu_live.live_decision.storage import list_live_decisions
        decisions = list_live_decisions(poller._backend, "AAPL", "strat_a")
        assert len(decisions) == 1
        assert decisions[0].decision == "EXECUTE"
        assert decisions[0].precondition_held is True
        assert "12 of 15" in decisions[0].reasoning
        assert decisions[0].raw_content == "EXECUTE -- full reasoning..."

    def test_a_failed_trigger_call_is_recorded_as_an_error_not_silently_lost(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=ConnectionError("agent down"))

        asyncio.run(poller.cycle())

        from vinu_live.live_decision.storage import list_live_decisions
        decisions = list_live_decisions(poller._backend, "AAPL", "strat_a")
        assert len(decisions) == 1
        assert decisions[0].decision == "error"
        assert "agent down" in decisions[0].reasoning

    def test_a_failed_trigger_call_is_logged_not_raised(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=ConnectionError("agent down"))

        result = asyncio.run(poller.cycle())  # must not raise
        assert result["candle_close_events"] == 1

        from vinu_live.live_decision.storage import get_stage_state
        state = get_stage_state(poller._backend, "AAPL", "strat_a")
        # Stays ready_to_execute -- retried next cycle, not silently lost.
        assert state.stage == "ready_to_execute"


def test_disabled_strategy_is_never_fetched(poller):
    async def _get(url, params=None, **kwargs):
        if "/strategy/strategies" in url and "/strategies/" not in url:
            return _resp(json_body=[{"name": "strat_a", "enabled": False}])
        raise AssertionError(f"disabled strategy should never be fetched: {url}")

    poller._http.get = AsyncMock(side_effect=_get)

    result = asyncio.run(poller.cycle())

    assert result["strategies_checked"] == 0
