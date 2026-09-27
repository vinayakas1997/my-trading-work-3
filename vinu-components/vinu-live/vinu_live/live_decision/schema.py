"""Dataclasses + table-name constants for the live decision loop.

Mirrors vinu_live/book/schema.py's own pattern (plain dataclasses +
table-name constants, storage/backend logic lives in storage.py) rather
than inventing a different convention for this new module.

Design reference: missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/reverse-engineering/
03-poller-and-state-schema.md
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

LIVE_POLL_CURSOR_TABLE = "live_poll_cursor"
STRATEGY_STAGE_STATE_TABLE = "strategy_stage_state"
STRATEGY_STAGE_TRANSITIONS_TABLE = "strategy_stage_transitions"
LIVE_DECISIONS_TABLE = "live_decisions"

Stage = Literal[
    "idle",
    "fired_awaiting_confirmation",
    "ready_to_execute",
    "executed",
    "expired",
]

# Stages after which the tracker resets to "idle" (clearing trigger_id)
# on the *next* evaluation, rather than staying terminal forever -- a
# must-condition can fire again later (03-poller-and-state-schema.md
# Part B: "these are terminal only for one trigger's lifecycle").
TERMINAL_STAGES: frozenset[Stage] = frozenset({"executed", "expired"})


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PollCursor:
    ticker: str
    timeframe: str
    last_processed_bar_ts: int
    updated_at: str = ""


@dataclass
class StageState:
    ticker: str
    strategy_id: str
    stage: Stage = "idle"
    trigger_id: str | None = None
    entered_stage_at: str = ""
    # An integer bar_ts cutoff (unix seconds), not a wall-clock string --
    # compared directly against the candle-close event's own bar_ts
    # (conditions.py-style numeric comparison), so grace-window expiry is
    # driven by real market time (candles), not wall-clock time.
    grace_window_expires_at: int | None = None
    last_checked_bar_ts: int | None = None
    updated_at: str = ""
    # Point 3's snapshot, from the candle-close event that produced
    # `last_checked_bar_ts` -- resolves 04-live-detector-schema.md's own
    # open question ("leaning toward persist it, not decided") in favor
    # of persisting: point 5's agent needs to read "what does this look
    # like right now" without recomputing it, and the transitions
    # history benefits from knowing what a past decision was made
    # against. Updated on every evaluation, not just real transitions.
    last_snapshot: dict[str, Any] = field(default_factory=dict)


def snapshot_to_json(snapshot: dict[str, Any]) -> str:
    return json.dumps(snapshot)


def snapshot_from_json(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return {}


@dataclass
class StageTransition:
    ticker: str
    strategy_id: str
    to_stage: Stage
    bar_ts: int
    reason: str
    from_stage: Stage | None = None
    trigger_id: str | None = None
    created_at: str = ""
    id: int | None = None


@dataclass
class LiveDecisionRecord:
    """The durable record of what live_decision_agent actually said --
    the gap this closes: previously the agent's full reasoning/verdict
    was computed (a real, evidence-grounded LLM call), returned over
    HTTP, logged at INFO level, and then gone -- nothing queryable kept
    it. Same "compute a real reason, then discard it" pattern the parent
    audit already found three times (item #21.3's RejectionRecord idea);
    this is that same fix applied to the live-decision loop's own
    verdicts, not a new pattern invented here."""
    ticker: str
    strategy_id: str
    trigger_id: str | None
    bar_ts: int
    decision: str  # "EXECUTE" | "SKIP" | "EXTEND_GRACE_WINDOW" | "error" | "unrecognized"
    precondition_held: bool | None
    reasoning: str
    raw_content: str
    recorded_at: str = ""
    id: int | None = None
    # Point 7 option 1 (06-execution-handoff-and-architecture.md): whether
    # LiveScheduler has already merged this EXECUTE decision into a real
    # cycle's target_weights. False for every non-EXECUTE decision too
    # (nothing else is ever "applied"), so the query that matters --
    # "which EXECUTE decisions still need to become an order" -- is a
    # single WHERE clause, not a join against some other table.
    applied: bool = False
    applied_at: str | None = None
