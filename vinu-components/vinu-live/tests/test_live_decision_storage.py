import os
import tempfile

import pytest

from vinu_live.live_decision.schema import LiveDecisionRecord, StageState, StageTransition
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    advance_cursor,
    get_cursor,
    get_stage_state,
    list_live_decisions,
    list_transitions,
    list_unapplied_executes,
    mark_decision_applied,
    record_live_decision,
    record_transition,
    save_stage_state,
)


@pytest.fixture
def backend():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    be = LiveDecisionBackend(db_path)
    yield be
    be.close()
    if os.path.exists(db_path):
        os.unlink(db_path)


def test_cursor_roundtrip(backend):
    assert get_cursor(backend, "AAPL", "15m") is None
    advance_cursor(backend, "AAPL", "15m", 1000)
    cursor = get_cursor(backend, "AAPL", "15m")
    assert cursor.last_processed_bar_ts == 1000
    advance_cursor(backend, "AAPL", "15m", 2000)
    cursor = get_cursor(backend, "AAPL", "15m")
    assert cursor.last_processed_bar_ts == 2000


def test_cursor_is_per_ticker_and_timeframe(backend):
    advance_cursor(backend, "AAPL", "15m", 1000)
    advance_cursor(backend, "AAPL", "1h", 5000)
    advance_cursor(backend, "MSFT", "15m", 2000)
    assert get_cursor(backend, "AAPL", "15m").last_processed_bar_ts == 1000
    assert get_cursor(backend, "AAPL", "1h").last_processed_bar_ts == 5000
    assert get_cursor(backend, "MSFT", "15m").last_processed_bar_ts == 2000


def test_unseen_pair_defaults_to_idle(backend):
    state = get_stage_state(backend, "AAPL", "sma_cross")
    assert state.stage == "idle"
    assert state.trigger_id is None


def test_save_and_reload_stage_state(backend):
    state = StageState(
        ticker="AAPL", strategy_id="sma_cross", stage="fired_awaiting_confirmation",
        trigger_id="trig_abc", entered_stage_at="2026-01-01T00:00:00+00:00",
        grace_window_expires_at=2000, last_checked_bar_ts=1000,
    )
    save_stage_state(backend, state)
    reloaded = get_stage_state(backend, "AAPL", "sma_cross")
    assert reloaded.stage == "fired_awaiting_confirmation"
    assert reloaded.trigger_id == "trig_abc"
    assert reloaded.grace_window_expires_at == 2000


def test_transitions_are_append_only_and_ordered(backend):
    record_transition(backend, StageTransition(
        ticker="AAPL", strategy_id="sma_cross", from_stage=None, to_stage="idle",
        bar_ts=100, reason="init",
    ))
    record_transition(backend, StageTransition(
        ticker="AAPL", strategy_id="sma_cross", from_stage="idle", to_stage="fired_awaiting_confirmation",
        trigger_id="trig_1", bar_ts=200, reason="must_condition_fired",
    ))
    transitions = list_transitions(backend, "AAPL", "sma_cross")
    assert len(transitions) == 2
    # Most recent first
    assert transitions[0].to_stage == "fired_awaiting_confirmation"
    assert transitions[1].to_stage == "idle"


def test_live_decisions_are_durably_recorded_not_just_logged(backend):
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="sma_cross", trigger_id="trig_1", bar_ts=1000,
        decision="EXECUTE", precondition_held=True,
        reasoning="ADX confirms momentum, 12 of 15 recorded triggers extended",
        raw_content="EXECUTE -- full reasoning here...",
    ))
    decisions = list_live_decisions(backend, "AAPL", "sma_cross")
    assert len(decisions) == 1
    d = decisions[0]
    assert d.decision == "EXECUTE"
    assert d.precondition_held is True
    assert "ADX confirms momentum" in d.reasoning
    assert d.raw_content == "EXECUTE -- full reasoning here..."
    assert d.trigger_id == "trig_1"
    assert d.recorded_at  # stamped, not blank


def test_live_decisions_survive_a_precondition_held_of_none(backend):
    """The agent can return no clear precondition_held (e.g. an error or
    EXTEND_GRACE_WINDOW outcome) -- must round-trip as None, not crash on
    the INTEGER<->bool conversion or silently coerce to False."""
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="sma_cross", trigger_id=None, bar_ts=1000,
        decision="error", precondition_held=None, reasoning="", raw_content="",
    ))
    d = list_live_decisions(backend, "AAPL", "sma_cross")[0]
    assert d.precondition_held is None


def test_live_decisions_are_queryable_by_ticker_across_strategies(backend):
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="sma_cross", trigger_id="t1", bar_ts=1000,
        decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
    ))
    record_live_decision(backend, LiveDecisionRecord(
        ticker="AAPL", strategy_id="rsi_reversal", trigger_id="t2", bar_ts=1000,
        decision="SKIP", precondition_held=False, reasoning="", raw_content="",
    ))
    all_for_aapl = list_live_decisions(backend, "AAPL")
    assert len(all_for_aapl) == 2
    only_sma_cross = list_live_decisions(backend, "AAPL", "sma_cross")
    assert len(only_sma_cross) == 1
    assert only_sma_cross[0].strategy_id == "sma_cross"


class TestUnappliedExecutes:
    """Point 7 option 1 (06-execution-handoff-and-architecture.md):
    LiveScheduler's own queue of EXECUTE decisions still needing to be
    folded into a real cycle's target_weights."""

    def test_fresh_decisions_default_to_unapplied(self, backend) -> None:
        record_live_decision(backend, LiveDecisionRecord(
            ticker="AAPL", strategy_id="sma_cross", trigger_id="t1", bar_ts=1000,
            decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
        ))
        pending = list_unapplied_executes(backend)
        assert len(pending) == 1
        assert pending[0].applied is False
        assert pending[0].applied_at is None

    def test_only_execute_decisions_are_returned_not_skip_or_error(self, backend) -> None:
        record_live_decision(backend, LiveDecisionRecord(
            ticker="AAPL", strategy_id="sma_cross", trigger_id="t1", bar_ts=1000,
            decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
        ))
        record_live_decision(backend, LiveDecisionRecord(
            ticker="MSFT", strategy_id="sma_cross", trigger_id="t2", bar_ts=1000,
            decision="SKIP", precondition_held=False, reasoning="", raw_content="",
        ))
        record_live_decision(backend, LiveDecisionRecord(
            ticker="GOOG", strategy_id="sma_cross", trigger_id="t3", bar_ts=1000,
            decision="error", precondition_held=None, reasoning="", raw_content="",
        ))
        pending = list_unapplied_executes(backend)
        assert len(pending) == 1
        assert pending[0].ticker == "AAPL"

    def test_mark_decision_applied_removes_it_from_the_pending_queue(self, backend) -> None:
        record_live_decision(backend, LiveDecisionRecord(
            ticker="AAPL", strategy_id="sma_cross", trigger_id="t1", bar_ts=1000,
            decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
        ))
        decision_id = list_unapplied_executes(backend)[0].id
        mark_decision_applied(backend, decision_id)

        assert list_unapplied_executes(backend) == []
        applied = list_live_decisions(backend, "AAPL", "sma_cross")[0]
        assert applied.applied is True
        assert applied.applied_at  # stamped, not blank

    def test_can_scope_the_pending_queue_to_one_ticker(self, backend) -> None:
        record_live_decision(backend, LiveDecisionRecord(
            ticker="AAPL", strategy_id="sma_cross", trigger_id="t1", bar_ts=1000,
            decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
        ))
        record_live_decision(backend, LiveDecisionRecord(
            ticker="MSFT", strategy_id="sma_cross", trigger_id="t2", bar_ts=1000,
            decision="EXECUTE", precondition_held=True, reasoning="", raw_content="",
        ))
        pending = list_unapplied_executes(backend, ticker="AAPL")
        assert len(pending) == 1
        assert pending[0].ticker == "AAPL"
