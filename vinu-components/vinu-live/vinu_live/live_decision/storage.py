"""SQLite storage for the live decision loop -- same SQLiteBackend
pattern vinu_live/book/positions.py already uses (see that file's
BookBackend), not a new storage convention.

Design reference: .../reverse-engineering/03-poller-and-state-schema.md
"""

from __future__ import annotations

import logging

from vinu_infra.sqlite import SQLiteBackend

from vinu_live.live_decision.schema import (
    LIVE_DECISIONS_TABLE,
    LIVE_POLL_CURSOR_TABLE,
    STRATEGY_STAGE_STATE_TABLE,
    STRATEGY_STAGE_TRANSITIONS_TABLE,
    LiveDecisionRecord,
    PollCursor,
    Stage,
    StageState,
    StageTransition,
    now_iso,
    snapshot_from_json,
    snapshot_to_json,
)

LOG = logging.getLogger(__name__)


class LiveDecisionBackend(SQLiteBackend):
    SCHEMA = f"""
        CREATE TABLE IF NOT EXISTS {LIVE_POLL_CURSOR_TABLE} (
            ticker TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            last_processed_bar_ts INTEGER NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (ticker, timeframe)
        );
        CREATE TABLE IF NOT EXISTS {STRATEGY_STAGE_STATE_TABLE} (
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            stage TEXT NOT NULL,
            trigger_id TEXT,
            entered_stage_at TEXT NOT NULL,
            grace_window_expires_at INTEGER,
            last_checked_bar_ts INTEGER,
            last_snapshot TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (ticker, strategy_id)
        );
        CREATE TABLE IF NOT EXISTS {STRATEGY_STAGE_TRANSITIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            from_stage TEXT,
            to_stage TEXT NOT NULL,
            trigger_id TEXT,
            bar_ts INTEGER NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_stage_transitions_lookup
            ON {STRATEGY_STAGE_TRANSITIONS_TABLE} (ticker, strategy_id, created_at);
        CREATE TABLE IF NOT EXISTS {LIVE_DECISIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            trigger_id TEXT,
            bar_ts INTEGER NOT NULL,
            decision TEXT NOT NULL,
            precondition_held INTEGER,
            reasoning TEXT,
            raw_content TEXT,
            recorded_at TEXT NOT NULL,
            applied INTEGER NOT NULL DEFAULT 0,
            applied_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_live_decisions_lookup
            ON {LIVE_DECISIONS_TABLE} (ticker, strategy_id, recorded_at);
        CREATE INDEX IF NOT EXISTS idx_live_decisions_unapplied
            ON {LIVE_DECISIONS_TABLE} (decision, applied);
    """
    SCHEMA_VERSION = 2
    # Point 7 option 1 (06-execution-handoff-and-architecture.md): lets
    # LiveScheduler find EXECUTE decisions it hasn't yet folded into a
    # real cycle's target_weights, on a database that may already exist
    # from before this fix landed.
    MIGRATIONS: list[tuple[str, str]] = [
        (f"ALTER TABLE {LIVE_DECISIONS_TABLE} ADD COLUMN applied INTEGER NOT NULL DEFAULT 0",
         "add applied flag to live_decisions"),
        (f"ALTER TABLE {LIVE_DECISIONS_TABLE} ADD COLUMN applied_at TEXT",
         "add applied_at to live_decisions"),
    ]


def init_live_decision_store(db_path: str = "data/live_decision.db") -> LiveDecisionBackend:
    return LiveDecisionBackend(db_path)


# --- live_poll_cursor -------------------------------------------------

def get_cursor(backend: LiveDecisionBackend, ticker: str, timeframe: str) -> PollCursor | None:
    conn = backend._get_conn()
    row = conn.execute(
        f"SELECT * FROM {LIVE_POLL_CURSOR_TABLE} WHERE ticker=? AND timeframe=?",
        (ticker, timeframe),
    ).fetchone()
    if row is None:
        return None
    return PollCursor(
        ticker=row["ticker"],
        timeframe=row["timeframe"],
        last_processed_bar_ts=row["last_processed_bar_ts"],
        updated_at=row["updated_at"],
    )


def advance_cursor(backend: LiveDecisionBackend, ticker: str, timeframe: str, bar_ts: int) -> None:
    backend.upsert(
        LIVE_POLL_CURSOR_TABLE,
        {
            "ticker": ticker,
            "timeframe": timeframe,
            "last_processed_bar_ts": bar_ts,
            "updated_at": now_iso(),
        },
        conflict_columns=["ticker", "timeframe"],
    )


# --- strategy_stage_state ----------------------------------------------

def get_stage_state(backend: LiveDecisionBackend, ticker: str, strategy_id: str) -> StageState:
    """Always returns a real StageState -- a pair never seen before is
    the same as freshly idle (03-poller-and-state-schema.md Part B step
    1: "create one at idle if this pair has never been seen before"),
    not persisted until its first real transition."""
    conn = backend._get_conn()
    row = conn.execute(
        f"SELECT * FROM {STRATEGY_STAGE_STATE_TABLE} WHERE ticker=? AND strategy_id=?",
        (ticker, strategy_id),
    ).fetchone()
    if row is None:
        return StageState(ticker=ticker, strategy_id=strategy_id, stage="idle")
    return StageState(
        ticker=row["ticker"],
        strategy_id=row["strategy_id"],
        stage=row["stage"],
        trigger_id=row["trigger_id"],
        entered_stage_at=row["entered_stage_at"],
        grace_window_expires_at=row["grace_window_expires_at"],
        last_checked_bar_ts=row["last_checked_bar_ts"],
        updated_at=row["updated_at"],
        last_snapshot=snapshot_from_json(row["last_snapshot"]),
    )


def save_stage_state(backend: LiveDecisionBackend, state: StageState) -> None:
    backend.upsert(
        STRATEGY_STAGE_STATE_TABLE,
        {
            "ticker": state.ticker,
            "strategy_id": state.strategy_id,
            "stage": state.stage,
            "trigger_id": state.trigger_id,
            "entered_stage_at": state.entered_stage_at,
            "grace_window_expires_at": state.grace_window_expires_at,
            "last_checked_bar_ts": state.last_checked_bar_ts,
            "last_snapshot": snapshot_to_json(state.last_snapshot),
            "updated_at": now_iso(),
        },
        conflict_columns=["ticker", "strategy_id"],
    )


# --- strategy_stage_transitions (append-only) ---------------------------

def record_transition(backend: LiveDecisionBackend, transition: StageTransition) -> None:
    """Only real transitions get a row -- a candle-close check that
    leaves the stage unchanged writes nothing, per the design doc's own
    rule, so this table stays a meaningful history, not one row per
    poll cycle regardless of whether anything happened."""
    conn = backend._get_conn()
    conn.execute(
        f"""INSERT INTO {STRATEGY_STAGE_TRANSITIONS_TABLE}
            (ticker, strategy_id, from_stage, to_stage, trigger_id, bar_ts, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            transition.ticker,
            transition.strategy_id,
            transition.from_stage,
            transition.to_stage,
            transition.trigger_id,
            transition.bar_ts,
            transition.reason,
            now_iso(),
        ),
    )
    conn.commit()


def list_transitions(
    backend: LiveDecisionBackend, ticker: str, strategy_id: str, limit: int = 50,
) -> list[StageTransition]:
    conn = backend._get_conn()
    rows = conn.execute(
        f"""SELECT * FROM {STRATEGY_STAGE_TRANSITIONS_TABLE}
            WHERE ticker=? AND strategy_id=? ORDER BY id DESC LIMIT ?""",
        (ticker, strategy_id, limit),
    ).fetchall()
    return [
        StageTransition(
            id=row["id"],
            ticker=row["ticker"],
            strategy_id=row["strategy_id"],
            from_stage=row["from_stage"],
            to_stage=row["to_stage"],
            trigger_id=row["trigger_id"],
            bar_ts=row["bar_ts"],
            reason=row["reason"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


# --- live_decisions (append-only) ---------------------------------------

def record_live_decision(backend: LiveDecisionBackend, record: LiveDecisionRecord) -> None:
    """Durably records every real live_decision_agent verdict -- EXECUTE,
    SKIP, EXTEND_GRACE_WINDOW, or even a failed/unrecognized call --
    closing the gap where this data was previously computed (a real LLM
    call grounded in real evidence) and then only logged, never kept
    anywhere queryable."""
    conn = backend._get_conn()
    conn.execute(
        f"""INSERT INTO {LIVE_DECISIONS_TABLE}
            (ticker, strategy_id, trigger_id, bar_ts, decision, precondition_held,
             reasoning, raw_content, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record.ticker,
            record.strategy_id,
            record.trigger_id,
            record.bar_ts,
            record.decision,
            None if record.precondition_held is None else int(record.precondition_held),
            record.reasoning,
            record.raw_content,
            now_iso(),
        ),
    )
    conn.commit()


def list_live_decisions(
    backend: LiveDecisionBackend, ticker: str, strategy_id: str | None = None, limit: int = 50,
) -> list[LiveDecisionRecord]:
    conn = backend._get_conn()
    if strategy_id is not None:
        rows = conn.execute(
            f"""SELECT * FROM {LIVE_DECISIONS_TABLE}
                WHERE ticker=? AND strategy_id=? ORDER BY id DESC LIMIT ?""",
            (ticker, strategy_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT * FROM {LIVE_DECISIONS_TABLE}
                WHERE ticker=? ORDER BY id DESC LIMIT ?""",
            (ticker, limit),
        ).fetchall()
    return [
        LiveDecisionRecord(
            id=row["id"],
            ticker=row["ticker"],
            strategy_id=row["strategy_id"],
            trigger_id=row["trigger_id"],
            bar_ts=row["bar_ts"],
            decision=row["decision"],
            precondition_held=None if row["precondition_held"] is None else bool(row["precondition_held"]),
            reasoning=row["reasoning"] or "",
            raw_content=row["raw_content"] or "",
            recorded_at=row["recorded_at"],
            applied=bool(row["applied"]),
            applied_at=row["applied_at"],
        )
        for row in rows
    ]


def list_unapplied_executes(
    backend: LiveDecisionBackend, ticker: str | None = None, limit: int = 100,
) -> list[LiveDecisionRecord]:
    """EXECUTE decisions LiveScheduler hasn't yet folded into a real
    cycle's target_weights (point 7 option 1). Only "EXECUTE" is ever
    relevant here -- SKIP/EXTEND_GRACE_WINDOW/error decisions have
    nothing for the scheduler to apply."""
    conn = backend._get_conn()
    if ticker is not None:
        rows = conn.execute(
            f"""SELECT * FROM {LIVE_DECISIONS_TABLE}
                WHERE ticker=? AND decision='EXECUTE' AND applied=0
                ORDER BY id ASC LIMIT ?""",
            (ticker, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            f"""SELECT * FROM {LIVE_DECISIONS_TABLE}
                WHERE decision='EXECUTE' AND applied=0
                ORDER BY id ASC LIMIT ?""",
            (limit,),
        ).fetchall()
    return [
        LiveDecisionRecord(
            id=row["id"],
            ticker=row["ticker"],
            strategy_id=row["strategy_id"],
            trigger_id=row["trigger_id"],
            bar_ts=row["bar_ts"],
            decision=row["decision"],
            precondition_held=None if row["precondition_held"] is None else bool(row["precondition_held"]),
            reasoning=row["reasoning"] or "",
            raw_content=row["raw_content"] or "",
            recorded_at=row["recorded_at"],
            applied=bool(row["applied"]),
            applied_at=row["applied_at"],
        )
        for row in rows
    ]


def mark_decision_applied(backend: LiveDecisionBackend, decision_id: int) -> None:
    conn = backend._get_conn()
    conn.execute(
        f"UPDATE {LIVE_DECISIONS_TABLE} SET applied=1, applied_at=? WHERE id=?",
        (now_iso(), decision_id),
    )
    conn.commit()
