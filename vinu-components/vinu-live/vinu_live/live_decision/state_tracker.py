"""Point 4: the stage/state tracker.

Implements the 5-state machine and per-candle-close evaluation logic
exactly as specified in .../reverse-engineering/
03-poller-and-state-schema.md Part B -- this module is the executable
version of that design doc, not a reinterpretation of it.

Replaces today's fully stateless condition evaluation (confirmed
stateless -- no memory across candles -- per 00-explanation.md's
citation of vinu_strategy/engine/condition_evaluator.py).
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from vinu_live.live_decision import conditions
from vinu_live.live_decision.schema import (
    TERMINAL_STAGES,
    Stage,
    StageState,
    StageTransition,
    now_iso,
)
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    get_stage_state,
    record_transition,
    save_stage_state,
)

LOG = logging.getLogger(__name__)


def _trigger_id(ticker: str, strategy_id: str, bar_ts: int) -> str:
    raw = f"{ticker}:{strategy_id}:{bar_ts}"
    return f"trig_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _transition(
    backend: LiveDecisionBackend,
    state: StageState,
    *,
    to_stage: Stage,
    bar_ts: int,
    reason: str,
    trigger_id: str | None,
    live_snapshot: dict[str, Any],
) -> StageState:
    record_transition(backend, StageTransition(
        ticker=state.ticker,
        strategy_id=state.strategy_id,
        from_stage=state.stage,
        to_stage=to_stage,
        trigger_id=trigger_id,
        bar_ts=bar_ts,
        reason=reason,
    ))
    new_state = StageState(
        ticker=state.ticker,
        strategy_id=state.strategy_id,
        stage=to_stage,
        trigger_id=trigger_id,
        entered_stage_at=now_iso(),
        grace_window_expires_at=None,
        last_checked_bar_ts=bar_ts,
        last_snapshot=live_snapshot,
    )
    return new_state


def evaluate_candle_close(
    backend: LiveDecisionBackend,
    *,
    ticker: str,
    strategy_id: str,
    bar_ts: int,
    timeframe_seconds: int,
    live_snapshot: dict[str, Any],
    must_conditions: list[dict[str, Any]],
    confirmation_conditions: list[dict[str, Any]],
    grace_window_bars: int,
) -> StageState:
    """One evaluation per candle-close event, per (ticker, strategy_id).
    Called by the poller (point 2) once per event it emits. Mutates
    storage as a side effect and returns the resulting state.

    `live_snapshot` is point 3's detector output; conditions are checked
    against it under source="live_indicators" (conditions.py's ctx
    shape).
    """
    state = get_stage_state(backend, ticker, strategy_id)
    ctx = {"live_indicators": live_snapshot}

    # Step 5: executed/expired reset to idle first, so a fresh
    # must-condition check can happen in the same event rather than
    # wasting a full cycle just resetting.
    if state.stage in TERMINAL_STAGES:
        state = _transition(
            backend, state, to_stage="idle", bar_ts=bar_ts,
            reason=f"reset_from_{state.stage}", trigger_id=None,
            live_snapshot=live_snapshot,
        )
        save_stage_state(backend, state)

    if state.stage == "idle":
        fired, _trace = conditions.evaluate_all(must_conditions, ctx)
        if not fired:
            # No transition -- still idle, no history row for a no-op check.
            state.last_checked_bar_ts = bar_ts
            state.last_snapshot = live_snapshot
            save_stage_state(backend, state)
            return state

        trigger_id = _trigger_id(ticker, strategy_id, bar_ts)
        if confirmation_conditions:
            new_state = _transition(
                backend, state, to_stage="fired_awaiting_confirmation",
                bar_ts=bar_ts, reason="must_condition_fired", trigger_id=trigger_id,
                live_snapshot=live_snapshot,
            )
            new_state.grace_window_expires_at = bar_ts + grace_window_bars * timeframe_seconds
        else:
            new_state = _transition(
                backend, state, to_stage="ready_to_execute",
                bar_ts=bar_ts, reason="must_condition_fired_no_confirmation_needed",
                trigger_id=trigger_id, live_snapshot=live_snapshot,
            )
        save_stage_state(backend, new_state)
        return new_state

    if state.stage == "fired_awaiting_confirmation":
        confirmed, _trace = conditions.evaluate_all(confirmation_conditions, ctx)
        if confirmed:
            new_state = _transition(
                backend, state, to_stage="ready_to_execute", bar_ts=bar_ts,
                reason="grace_window_confirmed", trigger_id=state.trigger_id,
                live_snapshot=live_snapshot,
            )
            save_stage_state(backend, new_state)
            return new_state

        expires_at = state.grace_window_expires_at
        if expires_at is not None and bar_ts > expires_at:
            new_state = _transition(
                backend, state, to_stage="expired", bar_ts=bar_ts,
                reason="grace_window_expired", trigger_id=state.trigger_id,
                live_snapshot=live_snapshot,
            )
            save_stage_state(backend, new_state)
            return new_state

        # Still waiting, not yet expired -- no transition row.
        state.last_checked_bar_ts = bar_ts
        state.last_snapshot = live_snapshot
        save_stage_state(backend, state)
        return state

    if state.stage == "ready_to_execute":
        # Step 4: do not re-evaluate must-conditions while a decision is
        # still pending on point 5's agent -- avoids a second
        # must-condition firing corrupting trigger_id attribution.
        state.last_checked_bar_ts = bar_ts
        state.last_snapshot = live_snapshot
        save_stage_state(backend, state)
        return state

    # Unreachable in practice (idle/fired_awaiting_confirmation/
    # ready_to_execute are the only non-terminal stages, and terminal
    # ones are reset above) -- kept as an explicit, loud failure rather
    # than silently falling through, since this is a live-trading state
    # machine.
    raise ValueError(f"evaluate_candle_close: unexpected stage {state.stage!r} for {ticker}/{strategy_id}")


def mark_executed(
    backend: LiveDecisionBackend, ticker: str, strategy_id: str, bar_ts: int,
    *, reason: str = "agent_executed",
) -> StageState:
    """Called once point 5's agent has actually returned a decision for a
    ready_to_execute pair -- not called by the state tracker itself,
    since the tracker only detects readiness, it doesn't decide (see
    05-deciding-agent-and-precondition-tracking.md's "structurally
    cannot act, only decide" posture for the agent this hands off to).

    Covers both EXECUTE and SKIP outcomes (pass reason="agent_skipped"
    for the latter) -- both resolve this trigger's lifecycle the same
    way (reset to idle on the next candle-close, per TERMINAL_STAGES),
    the only difference is which reason gets recorded in
    strategy_stage_transitions for the audit trail."""
    state = get_stage_state(backend, ticker, strategy_id)
    new_state = _transition(
        backend, state, to_stage="executed", bar_ts=bar_ts,
        reason=reason, trigger_id=state.trigger_id,
        live_snapshot=state.last_snapshot,
    )
    save_stage_state(backend, new_state)
    return new_state


def mark_expired(
    backend: LiveDecisionBackend, ticker: str, strategy_id: str, bar_ts: int,
    *, reason: str = "decision_attempts_exhausted",
) -> StageState:
    """Gives up on a ready_to_execute trigger whose live-decision call never
    produced a usable verdict (error / unrecognized / EXTEND_GRACE_WINDOW,
    repeatedly). `expired` is terminal for one trigger's lifecycle, so the pair
    resets to idle on the next candle close and a later must-condition firing
    gets a fresh trigger -- without this, a pair whose call kept failing stayed
    ready_to_execute forever (the tracker never re-evaluates a ready pair)."""
    state = get_stage_state(backend, ticker, strategy_id)
    new_state = _transition(
        backend, state, to_stage="expired", bar_ts=bar_ts,
        reason=reason, trigger_id=state.trigger_id,
        live_snapshot=state.last_snapshot,
    )
    save_stage_state(backend, new_state)
    return new_state
