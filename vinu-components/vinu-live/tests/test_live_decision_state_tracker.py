import os
import tempfile

import pytest

from vinu_live.live_decision.state_tracker import evaluate_candle_close, mark_executed
from vinu_live.live_decision.storage import LiveDecisionBackend, list_transitions

MUST_CONDITIONS = [{"source": "live_indicators", "key": "sma_5_gt_sma_50", "operator": "eq", "value": True}]
CONFIRMATION_CONDITIONS = [{"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20}]


@pytest.fixture
def backend():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = LiveDecisionBackend(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def _evaluate(backend, bar_ts, snapshot, must=MUST_CONDITIONS, confirm=CONFIRMATION_CONDITIONS, grace=3):
    return evaluate_candle_close(
        backend, ticker="AAPL", strategy_id="sma_cross", bar_ts=bar_ts,
        timeframe_seconds=900, live_snapshot=snapshot,
        must_conditions=must, confirmation_conditions=confirm, grace_window_bars=grace,
    )


def test_idle_stays_idle_when_must_condition_not_met(backend):
    state = _evaluate(backend, 1000, {"sma_5_gt_sma_50": False})
    assert state.stage == "idle"
    assert list_transitions(backend, "AAPL", "sma_cross") == []


def test_must_condition_fires_into_grace_window_when_confirmation_conditions_exist(backend):
    state = _evaluate(backend, 1000, {"sma_5_gt_sma_50": True, "adx_14": 15})
    assert state.stage == "fired_awaiting_confirmation"
    assert state.trigger_id is not None
    assert state.grace_window_expires_at == 1000 + 3 * 900
    transitions = list_transitions(backend, "AAPL", "sma_cross")
    assert len(transitions) == 1
    assert transitions[0].to_stage == "fired_awaiting_confirmation"
    assert transitions[0].reason == "must_condition_fired"


def test_must_condition_fires_straight_to_ready_when_no_confirmation_conditions(backend):
    state = _evaluate(backend, 1000, {"sma_5_gt_sma_50": True}, confirm=[])
    assert state.stage == "ready_to_execute"
    assert state.trigger_id is not None


def test_grace_window_confirms_into_ready_to_execute(backend):
    first = _evaluate(backend, 1000, {"sma_5_gt_sma_50": True, "adx_14": 15})
    assert first.stage == "fired_awaiting_confirmation"
    trigger_id = first.trigger_id

    second = _evaluate(backend, 1900, {"sma_5_gt_sma_50": True, "adx_14": 25})
    assert second.stage == "ready_to_execute"
    assert second.trigger_id == trigger_id  # same trigger carried through


def test_grace_window_expires_without_confirmation(backend):
    _evaluate(backend, 1000, {"sma_5_gt_sma_50": True, "adx_14": 15})
    # grace window is 3 * 900 = 2700s -> expires_at = 3700; bar_ts=3800 is past it
    expired = _evaluate(backend, 3800, {"sma_5_gt_sma_50": True, "adx_14": 5})
    assert expired.stage == "expired"

    transitions = list_transitions(backend, "AAPL", "sma_cross")
    reasons = [t.reason for t in transitions]
    assert "grace_window_expired" in reasons


def test_grace_window_not_yet_expired_stays_waiting(backend):
    _evaluate(backend, 1000, {"sma_5_gt_sma_50": True, "adx_14": 15})
    still_waiting = _evaluate(backend, 1500, {"sma_5_gt_sma_50": True, "adx_14": 15})
    assert still_waiting.stage == "fired_awaiting_confirmation"


def test_ready_to_execute_does_not_re_evaluate_must_conditions(backend):
    _evaluate(backend, 1000, {"sma_5_gt_sma_50": True}, confirm=[])
    ready = _evaluate(backend, 1900, {"sma_5_gt_sma_50": True}, confirm=[])
    assert ready.stage == "ready_to_execute"
    # No new transition rows beyond the original fire -- still just 1.
    transitions = list_transitions(backend, "AAPL", "sma_cross")
    assert len(transitions) == 1


def test_executed_resets_to_idle_on_next_candle_close_and_can_refire(backend):
    ready = _evaluate(backend, 1000, {"sma_5_gt_sma_50": True}, confirm=[])
    assert ready.stage == "ready_to_execute"
    mark_executed(backend, "AAPL", "sma_cross", 1000)

    # Next candle close: resets to idle, then must-condition is still
    # true so it fires again fresh, in the same event.
    refired = _evaluate(backend, 1900, {"sma_5_gt_sma_50": True}, confirm=[])
    assert refired.stage == "ready_to_execute"

    transitions = list_transitions(backend, "AAPL", "sma_cross")
    reasons = [t.reason for t in transitions]
    assert "agent_executed" in reasons
    assert "reset_from_executed" in reasons


def test_last_snapshot_is_persisted_on_every_evaluation(backend):
    """Point 5's agent needs to read 'what does this look like right
    now' without recomputing -- 04-live-detector-schema.md's open
    question, resolved in favor of persisting."""
    idle_state = _evaluate(backend, 1000, {"sma_5_gt_sma_50": False, "adx_14": 12})
    assert idle_state.last_snapshot == {"sma_5_gt_sma_50": False, "adx_14": 12}

    fired_state = _evaluate(backend, 1900, {"sma_5_gt_sma_50": True, "adx_14": 15})
    assert fired_state.last_snapshot == {"sma_5_gt_sma_50": True, "adx_14": 15}

    from vinu_live.live_decision.storage import get_stage_state
    reloaded = get_stage_state(backend, "AAPL", "sma_cross")
    assert reloaded.last_snapshot == {"sma_5_gt_sma_50": True, "adx_14": 15}


def test_expired_resets_to_idle_and_can_refire(backend):
    _evaluate(backend, 1000, {"sma_5_gt_sma_50": True, "adx_14": 15})
    _evaluate(backend, 3800, {"sma_5_gt_sma_50": True, "adx_14": 5})  # expires

    refired = _evaluate(backend, 4700, {"sma_5_gt_sma_50": True, "adx_14": 15})
    assert refired.stage == "fired_awaiting_confirmation"
