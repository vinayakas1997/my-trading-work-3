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
            if "/precondition-check" in url:
                return _resp(json_body={"status": "ok"})
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
            if "/precondition-check" in url:
                return _resp(json_body={"status": "ok"})
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


class TestPreconditionWriteBack:
    """Point 6's write-back path (missing-pieces-of-system/new-theory-
    of-trading/system-wide-audit-and-design/reverse-engineering/
    05-deciding-agent-and-precondition-tracking.md Part C): every real
    EXECUTE/SKIP live_decision_agent verdict must flip the strategy's
    own `precondition.tested` (vinu-strategy), regardless of which way
    it went."""

    def _strategies_resp(self, must_conditions):
        return {
            "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
            "must_conditions": must_conditions, "confirmation_conditions": [],
            "grace_window_bars": 5,
        }

    def _get(self, must_condition_value):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body=self._strategies_resp(
                    [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": must_condition_value}],
                ))
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(260))
            raise AssertionError(f"unexpected GET: {url}")
        return _get

    def test_execute_calls_precondition_check_with_the_real_value(self, poller):
        calls = []

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                return _resp(json_body={"status": "ok", "decision": "EXECUTE", "precondition_held": True, "reasoning": "ok"})
            if "/precondition-check" in url:
                calls.append((url, json))
                return _resp(json_body={"status": "ok"})
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=self._get(-999))
        poller._http.post = AsyncMock(side_effect=_post)

        asyncio.run(poller.cycle())

        assert len(calls) == 1
        url, body = calls[0]
        assert "/strategy/strategies/strat_a/precondition-check" in url
        assert body == {"precondition_held": True}

    def test_skip_also_calls_precondition_check_being_checked_and_failing_still_counts(self, poller):
        calls = []

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                return _resp(json_body={"status": "ok", "decision": "SKIP", "precondition_held": False, "reasoning": "no"})
            if "/precondition-check" in url:
                calls.append((url, json))
                return _resp(json_body={"status": "ok"})
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=self._get(-999))
        poller._http.post = AsyncMock(side_effect=_post)

        asyncio.run(poller.cycle())

        assert len(calls) == 1
        assert calls[0][1] == {"precondition_held": False}

    def test_extend_grace_window_does_not_call_precondition_check(self, poller):
        """Only applies to fired_awaiting_confirmation in practice, but
        verified directly regardless: no real EXECUTE/SKIP verdict was
        reached, so `tested` must not flip."""
        calls = []

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                return _resp(json_body={"status": "ok", "decision": "EXTEND_GRACE_WINDOW", "reasoning": "waiting"})
            if "/precondition-check" in url:
                calls.append((url, json))
                return _resp(json_body={"status": "ok"})
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=self._get(-999))
        poller._http.post = AsyncMock(side_effect=_post)

        asyncio.run(poller.cycle())

        assert calls == []

    def test_precondition_check_failure_does_not_crash_the_cycle(self, poller):
        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                return _resp(json_body={"status": "ok", "decision": "EXECUTE", "precondition_held": True, "reasoning": "ok"})
            if "/precondition-check" in url:
                raise ConnectionError("strategy service down")
            raise AssertionError(f"unexpected POST: {url}")

        poller._http.get = AsyncMock(side_effect=self._get(-999))
        poller._http.post = AsyncMock(side_effect=_post)

        result = asyncio.run(poller.cycle())  # must not raise

        from vinu_live.live_decision.storage import get_stage_state
        state = get_stage_state(poller._backend, "AAPL", "strat_a")
        # The main decision still resolved fully -- only the best-effort
        # write-back failed.
        assert state.stage == "executed"
        assert result["candle_close_events"] == 1


def test_disabled_strategy_is_never_fetched(poller):
    async def _get(url, params=None, **kwargs):
        if "/strategy/strategies" in url and "/strategies/" not in url:
            return _resp(json_body=[{"name": "strat_a", "enabled": False}])
        raise AssertionError(f"disabled strategy should never be fetched: {url}")

    poller._http.get = AsyncMock(side_effect=_get)

    result = asyncio.run(poller.cycle())

    assert result["strategies_checked"] == 0


class TestPresentDataRecording:
    """Item #5 (missing-pieces-of-system/new-theory-of-trading/
    system-wide-audit-and-design/
    02-open-questions-strategy-and-simulation.md): the poller is the one
    real place a live snapshot is computed today -- it must durably
    record it, not just hand it to the state tracker and discard it."""

    def test_a_fresh_candle_close_records_a_live_snapshot(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)

        asyncio.run(poller.cycle())

        from vinu_live.live_decision.storage import get_latest_snapshot
        record = get_latest_snapshot(poller._backend, "AAPL", "live_indicators")
        assert record is not None
        assert record.granularity == "15m"
        assert record.snapshot_data  # real indicator values, not empty

    def test_no_fresh_candle_close_does_not_record_a_new_snapshot(self, poller):
        from vinu_live.live_decision.storage import advance_cursor, list_snapshots

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
        advance_cursor(poller._backend, "AAPL", "15m", 1000 + 900)  # matches _bars(2)'s last ts

        asyncio.run(poller.cycle())

        assert list_snapshots(poller._backend, "AAPL", "live_indicators") == []


def _bars_with_jump(n: int, jump: float = 50.0, start_ts: int = 1_700_000_000, step: int = 900):
    """Same shape as `_bars()`, but the final bar's close jumps hard
    relative to the rest of the series -- big enough to clear the
    2xATR(14) move-detection floor given this series' otherwise-constant
    ~2.0 true range."""
    body = _bars(n, start_ts=start_ts, step=step)
    last = body["data"][-1]
    last["close"] = last["close"] + jump
    last["high"] = last["close"] + 1.0
    last["low"] = last["close"] - 1.0
    return body


class TestMoveEventRecording:
    """item #10 (system-wide-audit-and-design/
    02-open-questions-strategy-and-simulation.md): Track 2's move check
    must run every cycle for every (ticker, timeframe) group, whether or
    not any strategy's must-condition also fires -- otherwise a real move
    on an unwatched condition is invisible forever."""

    def test_a_real_move_posts_a_move_event(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars_with_jump(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())

        assert poller._http.post.await_count == 1
        call = poller._http.post.await_args
        assert call.args[0] == f"{poller._config.research_api_url}/research/move-evidence/AAPL"
        payload = call.kwargs["json"]
        assert payload["granularity"] == "15m"
        assert payload["window_seconds"] == 900
        assert payload["direction"] == "up"
        assert payload["price_move"] > 0

    def test_no_real_move_does_not_post(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))  # no jump
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())

        poller._http.post.assert_not_awaited()

    def test_move_post_failure_does_not_break_the_cycle(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars_with_jump(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=Exception("connection refused"))

        result = asyncio.run(poller.cycle())

        assert result["candle_close_events"] == 1


class TestSignalEvidenceTriggerRecording:
    """The SignalEvidenceStore writer gap (found while building item #10,
    system-wide-audit-and-design/02-open-questions-strategy-and-
    simulation.md): nothing in this codebase ever called
    POST /research/signal-evidence/trigger in production -- this is that
    writer, called exactly once per real must-condition firing."""

    _FIRING_CONDITION = {"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}

    def test_a_fresh_must_condition_firing_posts_a_signal_evidence_trigger(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [self._FIRING_CONDITION],
                    "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())

        signal_evidence_calls = [
            c for c in poller._http.post.await_args_list
            if c.args[0].endswith("/research/signal-evidence/trigger")
        ]
        assert len(signal_evidence_calls) == 1
        payload = signal_evidence_calls[0].kwargs["json"]
        assert payload["symbol"] == "AAPL"
        assert payload["must_condition"] == ["live_indicators.adx_14_gt_-999"]
        assert payload["trigger_id"]
        assert payload["indicators"]  # the real live snapshot, not empty

    def test_no_must_conditions_configured_does_not_post(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [], "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())

        signal_evidence_calls = [
            c for c in poller._http.post.await_args_list
            if c.args[0].endswith("/research/signal-evidence/trigger")
        ]
        assert signal_evidence_calls == []

    def test_a_condition_that_never_fires_does_not_post(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [
                        {"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 999},
                    ],
                    "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())

        signal_evidence_calls = [
            c for c in poller._http.post.await_args_list
            if c.args[0].endswith("/research/signal-evidence/trigger")
        ]
        assert signal_evidence_calls == []

    def test_staying_in_ready_to_execute_across_cycles_only_posts_once(self, poller):
        """A pair that reaches ready_to_execute stays there across cycles
        (state_tracker's own "do not re-evaluate must-conditions" rule)
        -- the trigger_id doesn't change, so this must not re-post every
        cycle."""
        call_count = {"n": 0}

        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [self._FIRING_CONDITION],
                    "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                call_count["n"] += 1
                limit = (params or {}).get("limit", 2)
                start_ts = 1_700_000_000 + (call_count["n"] // 2) * 900
                return _resp(json_body=_bars(min(limit, 260), start_ts=start_ts))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(return_value=_resp(json_body={"status": "recorded"}))

        asyncio.run(poller.cycle())
        asyncio.run(poller.cycle())

        signal_evidence_calls = [
            c for c in poller._http.post.await_args_list
            if c.args[0].endswith("/research/signal-evidence/trigger")
        ]
        assert len(signal_evidence_calls) == 1

    def test_post_failure_does_not_break_the_cycle(self, poller):
        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": [self._FIRING_CONDITION],
                    "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                limit = (params or {}).get("limit", 2)
                return _resp(json_body=_bars(min(limit, 260)))
            raise AssertionError(f"unexpected URL: {url}")

        poller._http.get = AsyncMock(side_effect=_get)
        poller._http.post = AsyncMock(side_effect=Exception("connection refused"))

        result = asyncio.run(poller.cycle())

        assert result["candle_close_events"] == 1


class TestPositionReview:
    """The exit-mechanism fix (missing-pieces-of-system/new-theory-of-
    trading/system-wide-audit-and-design/
    04-synthesis-built-vs-missing-2026-09-28.md): a live_decision-opened
    position previously had no way to ever close on purpose. This
    re-invokes live_decision_agent (mode="review") on a bar-count cadence
    for every open position, asking HOLD/EXIT."""

    def _seed_position(self, poller, *, ticker="AAPL", strategy_id="strat_a",
                        opened_bar_ts=1000, timeframe="1h"):
        from vinu_live.live_decision.storage import advance_cursor, open_position
        pos = open_position(
            poller._backend, ticker=ticker, strategy_id=strategy_id,
            position_size=0.05, opened_bar_ts=opened_bar_ts,
        )
        advance_cursor(poller._backend, ticker, timeframe, opened_bar_ts)
        return pos

    def _strategy_by_id(self, strategy_id="strat_a", timeframe="1h"):
        return {strategy_id: {"name": strategy_id, "schedule": timeframe}}

    def test_below_cadence_is_not_reviewed(self, poller):
        pos = self._seed_position(poller)
        from vinu_live.live_decision.storage import advance_cursor
        # Cadence is 5 bars * 3600s = 18000s; only 1000s elapsed.
        advance_cursor(poller._backend, "AAPL", "1h", pos.opened_bar_ts + 1000)
        poller._http.post = AsyncMock(side_effect=AssertionError("should never POST below cadence"))

        reviewed = asyncio.run(poller._review_open_positions(self._strategy_by_id()))

        assert reviewed == 0

    def test_past_cadence_triggers_review_and_hold_keeps_it_open(self, poller):
        pos = self._seed_position(poller)
        from vinu_live.live_decision.storage import advance_cursor, list_open_positions
        advance_cursor(poller._backend, "AAPL", "1h", pos.opened_bar_ts + 18000)

        async def _post(url, json=None, **kwargs):
            assert "/agent/live-decision/run" in url
            assert json["mode"] == "review"
            assert json["ticker"] == "AAPL"
            assert json["strategy_id"] == "strat_a"
            assert json["position_context"]["position_size"] == 0.05
            return _resp(json_body={"status": "ok", "decision": "HOLD", "reasoning": "thesis intact"})

        poller._http.post = AsyncMock(side_effect=_post)

        reviewed = asyncio.run(poller._review_open_positions(self._strategy_by_id()))

        assert reviewed == 1
        still_open = list_open_positions(poller._backend)
        assert len(still_open) == 1
        assert still_open[0].last_reviewed_bar_ts == pos.opened_bar_ts + 18000

        from vinu_live.live_decision.storage import list_live_decisions
        decisions = list_live_decisions(poller._backend, "AAPL", "strat_a")
        assert len(decisions) == 1
        assert decisions[0].decision == "HOLD"
        assert decisions[0].trigger_id == f"pos_{pos.id}"

    def test_past_cadence_triggers_review_and_exit_closes_it(self, poller):
        pos = self._seed_position(poller)
        from vinu_live.live_decision.storage import advance_cursor, list_open_positions
        advance_cursor(poller._backend, "AAPL", "1h", pos.opened_bar_ts + 18000)

        poller._http.post = AsyncMock(return_value=_resp(json_body={
            "status": "ok", "decision": "EXIT", "reasoning": "precondition no longer holds",
        }))

        reviewed = asyncio.run(poller._review_open_positions(self._strategy_by_id()))

        assert reviewed == 1
        assert list_open_positions(poller._backend) == []
        closed = list_open_positions(poller._backend, status="closed")
        assert len(closed) == 1
        assert closed[0].closed_reason == "precondition no longer holds"

    def test_failed_review_call_leaves_last_reviewed_unchanged_to_retry(self, poller):
        pos = self._seed_position(poller)
        from vinu_live.live_decision.storage import advance_cursor, list_live_decisions, list_open_positions
        advance_cursor(poller._backend, "AAPL", "1h", pos.opened_bar_ts + 18000)

        poller._http.post = AsyncMock(side_effect=ConnectionError("agent down"))

        reviewed = asyncio.run(poller._review_open_positions(self._strategy_by_id()))

        assert reviewed == 1  # counted as "attempted this cycle"
        still_open = list_open_positions(poller._backend)
        assert still_open[0].last_reviewed_bar_ts is None  # unchanged -- retries next cycle

        decisions = list_live_decisions(poller._backend, "AAPL", "strat_a")
        assert decisions[0].decision == "error"
        assert "agent down" in decisions[0].reasoning

    def test_unknown_strategy_is_left_open_and_unreviewed(self, poller):
        self._seed_position(poller)
        poller._http.post = AsyncMock(side_effect=AssertionError("should never POST"))

        reviewed = asyncio.run(poller._review_open_positions({}))

        assert reviewed == 0
