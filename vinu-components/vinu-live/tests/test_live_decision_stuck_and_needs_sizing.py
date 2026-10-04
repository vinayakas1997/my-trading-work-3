"""v1 C1 + C2 of the-inconsistencies-v2 (plan item 2.4).

C1 -- and a worse bug found while fixing it: when the live-decision call
failed (HTTP error / timeout) or came back unrecognized, the pair stayed
`ready_to_execute` FOREVER. The poller only triggers on a fresh transition
INTO that stage, and the state tracker deliberately never re-evaluates a
ready pair, so the log's "will retry next cycle" was false and that
(ticker, strategy) could never fire again. Now it retries on later candles,
bounded, then expires the trigger, records why and notifies.

C2 -- an EXECUTE with no configured `live_decision_position_size` was marked
applied and forgotten. `list_needs_sizing` + `GET /live/decisions/needs-sizing`
make that queue visible; it is a read-time anti-join, so no new table.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from vinu_live.config import LiveConfig
from vinu_live.live_decision import state_tracker
from vinu_live.live_decision.poller import CandleClosePoller
from vinu_live.live_decision.schema import LiveDecisionRecord
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    count_unresolved_decision_attempts,
    get_stage_state,
    list_live_decisions,
    list_needs_sizing,
    mark_decision_applied,
    open_position,
    close_position,
    record_live_decision,
)
from vinu_live.server.app import create_app

STEP = 900


# ------------------------------------------------------------------ helpers

def _resp(status_code=200, json_body=None):
    r = MagicMock()
    r.status_code = status_code
    r.json.return_value = json_body if json_body is not None else {}
    r.raise_for_status = MagicMock()
    if status_code >= 400:
        r.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return r


def _bars(n: int, start_ts: int):
    return {
        "count": n,
        "data": [
            {"open": 100.0 + i, "high": 101.0 + i, "low": 99.0 + i, "close": 100.5 + i,
             "volume": 1000.0, "ts": start_ts + i * STEP}
            for i in range(n)
        ],
    }


@pytest.fixture
def backend():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    b = LiveDecisionBackend(path)
    yield b
    b.close()
    for suffix in ("", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.unlink(path + suffix)


def _rec(backend, decision, trigger_id="t1", ticker="AAPL", strategy="s1", bar_ts=1) -> int:
    record_live_decision(backend, LiveDecisionRecord(
        ticker=ticker, strategy_id=strategy, trigger_id=trigger_id, bar_ts=bar_ts,
        decision=decision, precondition_held=None, reasoning=f"{decision} reasoning", raw_content="",
    ))
    return list_live_decisions(backend, ticker, strategy, limit=1)[0].id


# ------------------------------------------------------------------ storage: attempts

def test_only_unresolved_outcomes_count_as_attempts(backend):
    for d in ("error", "unrecognized", "EXTEND_GRACE_WINDOW"):
        _rec(backend, d)
    assert count_unresolved_decision_attempts(backend, "AAPL", "s1", "t1") == 3
    _rec(backend, "SKIP")
    _rec(backend, "EXECUTE")
    assert count_unresolved_decision_attempts(backend, "AAPL", "s1", "t1") == 3  # resolved ones don't count


def test_attempts_are_scoped_to_one_trigger_and_pair(backend):
    _rec(backend, "error", trigger_id="t1")
    _rec(backend, "error", trigger_id="t2")
    _rec(backend, "error", trigger_id="t1", strategy="other")
    _rec(backend, "error", trigger_id="t1", ticker="MSFT")
    assert count_unresolved_decision_attempts(backend, "AAPL", "s1", "t1") == 1
    assert count_unresolved_decision_attempts(backend, "AAPL", "s1", "nope") == 0


def test_null_trigger_id_is_counted_by_null_safe_equality(backend):
    _rec(backend, "error", trigger_id=None)
    assert count_unresolved_decision_attempts(backend, "AAPL", "s1", None) == 1


# ------------------------------------------------------------------ storage: needs sizing

def test_applied_execute_without_a_position_needs_sizing(backend):
    did = _rec(backend, "EXECUTE")
    mark_decision_applied(backend, did)
    got = list_needs_sizing(backend)
    assert [r.trigger_id for r in got] == ["t1"] and got[0].decision == "EXECUTE"


def test_not_listed_when_unapplied_or_not_an_execute(backend):
    _rec(backend, "EXECUTE", trigger_id="unapplied")  # scheduler hasn't looked at it yet
    mark_decision_applied(backend, _rec(backend, "SKIP", trigger_id="skip"))
    mark_decision_applied(backend, _rec(backend, "error", trigger_id="err"))
    assert list_needs_sizing(backend) == []


def test_drains_once_a_position_exists_open_or_closed(backend):
    a = _rec(backend, "EXECUTE", trigger_id="ta")
    b = _rec(backend, "EXECUTE", trigger_id="tb")
    mark_decision_applied(backend, a)
    mark_decision_applied(backend, b)
    assert {r.trigger_id for r in list_needs_sizing(backend)} == {"ta", "tb"}

    open_position(backend, ticker="AAPL", strategy_id="s1", position_size=0.05, opened_bar_ts=1, trigger_id="ta")
    assert {r.trigger_id for r in list_needs_sizing(backend)} == {"tb"}

    pos = open_position(backend, ticker="AAPL", strategy_id="s1", position_size=0.05, opened_bar_ts=1, trigger_id="tb")
    close_position(backend, pos.id, reason="done", bar_ts=2)  # a closed position still means it WAS sized
    assert list_needs_sizing(backend) == []


def test_needs_sizing_is_newest_first_and_limited(backend):
    for i in range(5):
        mark_decision_applied(backend, _rec(backend, "EXECUTE", trigger_id=f"t{i}"))
    got = list_needs_sizing(backend, limit=3)
    assert [r.trigger_id for r in got] == ["t4", "t3", "t2"]


# ------------------------------------------------------------------ state tracker

def test_mark_expired_resets_the_pair_so_it_can_fire_again(backend):
    firing = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}]
    snap = {"adx_14": 25.0}

    def _eval(bar_ts):
        return state_tracker.evaluate_candle_close(
            backend, ticker="AAPL", strategy_id="s1", bar_ts=bar_ts, timeframe_seconds=STEP,
            live_snapshot=snap, must_conditions=firing, confirmation_conditions=[], grace_window_bars=5,
        )

    first = _eval(1000)
    assert first.stage == "ready_to_execute"
    assert _eval(1000 + STEP).stage == "ready_to_execute"  # the tracker never leaves it by itself

    state_tracker.mark_expired(backend, "AAPL", "s1", 1000 + 2 * STEP)
    assert get_stage_state(backend, "AAPL", "s1").stage == "expired"

    again = _eval(1000 + 3 * STEP)  # terminal -> idle -> re-fires with a NEW trigger
    assert again.stage == "ready_to_execute" and again.trigger_id != first.trigger_id


# ------------------------------------------------------------------ poller (end to end)

_FIRING = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": -999}]


class _Harness:
    """Drives CandleClosePoller.cycle() with a fake world: bars advance one
    candle per cycle; the agent endpoint answers from a scripted list."""

    def __init__(self, agent_script, config=None, notify_fails=False):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            self.db_path = f.name
        self.backend = LiveDecisionBackend(self.db_path)
        self.poller = CandleClosePoller(config or LiveConfig(), backend=self.backend)
        self.poller._http = MagicMock()
        self.clock = {"start": 1_700_000_000}
        self.script = list(agent_script)
        self.agent_calls = 0
        self.notifications: list[dict] = []
        self.notify_fails = notify_fails

        async def _get(url, params=None, **kwargs):
            if "/strategy/strategies/strat_a" in url:
                return _resp(json_body={
                    "name": "strat_a", "schedule": "15m", "universe": ["AAPL"],
                    "must_conditions": _FIRING, "confirmation_conditions": [], "grace_window_bars": 5,
                })
            if "/strategy/strategies" in url:
                return _resp(json_body=[{"name": "strat_a", "enabled": True}])
            if "/stock/candles/AAPL" in url:
                return _resp(json_body=_bars(min((params or {}).get("limit", 2), 260), self.clock["start"]))
            raise AssertionError(f"unexpected GET: {url}")

        async def _post(url, json=None, **kwargs):
            if "/agent/live-decision/run" in url:
                self.agent_calls += 1
                step = self.script.pop(0) if self.script else "fail"
                if step == "fail":
                    return _resp(status_code=500)
                return _resp(json_body={"status": "ok", "decision": step, "reasoning": f"agent said {step}"})
            if url.endswith("/agent/notify/reconciliation-drift"):
                if self.notify_fails:
                    raise RuntimeError("notify down")
                self.notifications.append(json)
                return _resp(json_body={"status": "ok"})
            return _resp(json_body={"status": "ok"})  # signal-evidence, precondition-check, move-evidence...

        self.poller._http.get = AsyncMock(side_effect=_get)
        self.poller._http.post = AsyncMock(side_effect=_post)

    def cycle(self):
        out = asyncio.run(self.poller.cycle())
        self.clock["start"] += STEP  # next cycle sees one new candle
        return out

    def stage(self):
        return get_stage_state(self.backend, "AAPL", "strat_a").stage

    def close(self):
        self.backend.close()
        for suffix in ("", "-wal", "-shm"):
            if os.path.exists(self.db_path + suffix):
                os.unlink(self.db_path + suffix)


@pytest.fixture
def harness_factory():
    made = []

    def make(*a, **kw):
        h = _Harness(*a, **kw)
        made.append(h)
        return h

    yield make
    for h in made:
        h.close()


def test_a_failed_call_is_retried_on_later_candles_instead_of_sticking_forever(harness_factory):
    h = harness_factory(["fail", "EXECUTE"])
    h.cycle()
    assert h.stage() == "ready_to_execute" and h.agent_calls == 1  # first attempt failed
    h.cycle()  # BEFORE the fix this cycle made no call at all and the pair stayed here forever
    assert h.agent_calls == 2
    assert h.stage() == "executed"
    assert h.notifications == []


def test_gives_up_after_the_limit_expires_the_trigger_notifies_and_unsticks_the_pair(harness_factory):
    h = harness_factory(["fail", "fail", "fail", "EXECUTE"])  # 4th call (a later, fresh trigger) succeeds
    h.cycle(); h.cycle(); h.cycle()
    assert h.agent_calls == 3 and h.stage() == "ready_to_execute"  # three real attempts, all unresolved

    h.cycle()  # attempts (3) >= limit (3): no more agent calls, trigger expires, one notification
    assert h.agent_calls == 3
    assert h.stage() == "expired"
    assert len(h.notifications) == 1
    note = h.notifications[0]
    assert note["action"] == "live_decision_stuck" and note["symbol"] == "AAPL/strat_a"
    assert "gave up after 3" in note["detail"]
    gave_up = [r for r in list_live_decisions(h.backend, "AAPL", "strat_a") if "gave up" in r.reasoning]
    assert len(gave_up) == 1 and gave_up[0].decision == "error"

    h.cycle()  # expired -> idle -> the must-condition fires again with a NEW trigger -> succeeds
    assert h.agent_calls == 4 and h.stage() == "executed"


def test_extend_grace_window_and_unrecognized_also_count_as_unresolved(harness_factory):
    h = harness_factory(["EXTEND_GRACE_WINDOW", "garbage", "fail"])
    for _ in range(4):
        h.cycle()
    assert h.stage() == "expired" and h.agent_calls == 3 and len(h.notifications) == 1


def test_limit_zero_restores_the_old_never_retry_behaviour(harness_factory):
    h = harness_factory(["fail"], config=LiveConfig(live_decision_max_trigger_attempts=0))
    for _ in range(4):
        h.cycle()
    assert h.agent_calls == 1 and h.stage() == "ready_to_execute" and h.notifications == []


def test_a_notification_failure_does_not_stop_the_expiry(harness_factory):
    h = harness_factory(["fail", "fail", "fail"], notify_fails=True)
    for _ in range(4):
        h.cycle()
    assert h.stage() == "expired"


def test_a_resolved_trigger_is_never_retried(harness_factory):
    h = harness_factory(["SKIP"])
    h.cycle()
    assert h.stage() == "executed" and h.agent_calls == 1
    h.cycle()  # resets to idle, re-fires with a NEW trigger -- that is one new call, not a retry of the old one
    assert h.agent_calls == 2


# ------------------------------------------------------------------ server route

def test_needs_sizing_route_lists_and_drains(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    seed = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
    mark_decision_applied(seed, _rec(seed, "EXECUTE", trigger_id="ta"))
    seed.close()

    with patch("vinu_live.server.app.load_config", return_value=config):
        client = TestClient(create_app())
        body = client.get("/live/decisions/needs-sizing").json()
        assert body["status"] == "ok" and body["count"] == 1
        assert body["decisions"][0]["trigger_id"] == "ta" and "live_decision_position_size" in body["hint"]

        seed = LiveDecisionBackend(str(tmp_path / "live_decision.db"))
        open_position(seed, ticker="AAPL", strategy_id="s1", position_size=0.05, opened_bar_ts=1, trigger_id="ta")
        seed.close()
        assert client.get("/live/decisions/needs-sizing").json()["count"] == 0


def test_needs_sizing_route_does_not_shadow_the_per_pair_route(tmp_path):
    config = LiveConfig(data_root=tmp_path)
    with patch("vinu_live.server.app.load_config", return_value=config):
        client = TestClient(create_app())
        pair = client.get("/live/decisions/AAPL/s1").json()
        assert pair["ticker"] == "AAPL" and pair["strategy_id"] == "s1"
