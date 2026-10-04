"""SQLite storage for the live decision loop -- same SQLiteBackend
pattern vinu_live/book/positions.py already uses (see that file's
BookBackend), not a new storage convention.

Design reference: .../reverse-engineering/03-poller-and-state-schema.md
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

from vinu_live.live_decision.schema import (
    LIVE_DECISION_OPEN_POSITIONS_TABLE,
    LIVE_DECISIONS_TABLE,
    LIVE_POLL_CURSOR_TABLE,
    LIVE_SNAPSHOTS_TABLE,
    STRATEGY_STAGE_STATE_TABLE,
    STRATEGY_STAGE_TRANSITIONS_TABLE,
    LiveDecisionOpenPosition,
    LiveDecisionRecord,
    LiveSnapshotRecord,
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
        CREATE TABLE IF NOT EXISTS {LIVE_DECISION_OPEN_POSITIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            position_size REAL NOT NULL,
            opened_bar_ts INTEGER NOT NULL,
            trigger_id TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            opened_at TEXT NOT NULL,
            last_reviewed_bar_ts INTEGER,
            closed_at TEXT,
            closed_bar_ts INTEGER,
            closed_reason TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_live_decision_open_positions_status
            ON {LIVE_DECISION_OPEN_POSITIONS_TABLE} (status, ticker, strategy_id);
        CREATE TABLE IF NOT EXISTS {LIVE_SNAPSHOTS_TABLE} (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol         TEXT NOT NULL,
            angle_name     TEXT NOT NULL,
            granularity    TEXT NOT NULL,
            computed_at    TEXT NOT NULL,
            snapshot_data  TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_live_snapshots_lookup
            ON {LIVE_SNAPSHOTS_TABLE} (symbol, angle_name, computed_at);
    """
    SCHEMA_VERSION = 6
    # Point 7 option 1 (06-execution-handoff-and-architecture.md): lets
    # LiveScheduler find EXECUTE decisions it hasn't yet folded into a
    # real cycle's target_weights, on a database that may already exist
    # from before this fix landed.
    MIGRATIONS: list[tuple[str, str]] = [
        (f"ALTER TABLE {LIVE_DECISIONS_TABLE} ADD COLUMN applied INTEGER NOT NULL DEFAULT 0",
         "add applied flag to live_decisions"),
        (f"ALTER TABLE {LIVE_DECISIONS_TABLE} ADD COLUMN applied_at TEXT",
         "add applied_at to live_decisions"),
        (f"""CREATE TABLE IF NOT EXISTS {LIVE_DECISION_OPEN_POSITIONS_TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            strategy_id TEXT NOT NULL,
            position_size REAL NOT NULL,
            opened_bar_ts INTEGER NOT NULL,
            trigger_id TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            opened_at TEXT NOT NULL,
            last_reviewed_bar_ts INTEGER,
            closed_at TEXT,
            closed_bar_ts INTEGER,
            closed_reason TEXT
        )""", "add live_decision_open_positions table (exit-mechanism fix)"),
        (f"""CREATE INDEX IF NOT EXISTS idx_live_decision_open_positions_status
            ON {LIVE_DECISION_OPEN_POSITIONS_TABLE} (status, ticker, strategy_id)""",
         "add status index to live_decision_open_positions"),
        (f"""CREATE TABLE IF NOT EXISTS {LIVE_SNAPSHOTS_TABLE} (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol         TEXT NOT NULL,
            angle_name     TEXT NOT NULL,
            granularity    TEXT NOT NULL,
            computed_at    TEXT NOT NULL,
            snapshot_data  TEXT NOT NULL
        )""", "add live_snapshots table (present-data recording, item #5)"),
        (f"""CREATE INDEX IF NOT EXISTS idx_live_snapshots_lookup
            ON {LIVE_SNAPSHOTS_TABLE} (symbol, angle_name, computed_at)""",
         "add lookup index to live_snapshots"),
        (f"ALTER TABLE {LIVE_DECISION_OPEN_POSITIONS_TABLE} ADD COLUMN entry_price REAL",
         "add entry_price to live_decision_open_positions (rule-based stop reference, audit A3)"),
        (f"ALTER TABLE {LIVE_DECISION_OPEN_POSITIONS_TABLE} ADD COLUMN exit_price REAL",
         "add exit_price to live_decision_open_positions (a loss leaves a number, features-logic-checking F3)"),
        (f"ALTER TABLE {LIVE_DECISION_OPEN_POSITIONS_TABLE} ADD COLUMN return_pct REAL",
         "add return_pct to live_decision_open_positions (reference return at the exit)"),
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


def _row_to_decision(row: Any) -> LiveDecisionRecord:
    return LiveDecisionRecord(
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


def count_unresolved_decision_attempts(
    backend: LiveDecisionBackend, ticker: str, strategy_id: str, trigger_id: str | None,
) -> int:
    """How many times this trigger's live-decision call produced NO usable
    verdict (error, unrecognized, EXTEND_GRACE_WINDOW). Read from the existing
    append-only live_decisions table -- no counter column to keep in sync.
    EXECUTE / SKIP resolve a trigger, so they never count as unresolved."""
    conn = backend._get_conn()
    row = conn.execute(
        f"""SELECT COUNT(*) AS n FROM {LIVE_DECISIONS_TABLE}
            WHERE ticker=? AND strategy_id=? AND trigger_id IS ?
              AND decision NOT IN ('EXECUTE', 'SKIP')""",
        (ticker, strategy_id, trigger_id),
    ).fetchone()
    return int(row["n"])


def list_needs_sizing(backend: LiveDecisionBackend, limit: int = 100) -> list[LiveDecisionRecord]:
    """EXECUTE decisions that were marked applied but never became a position
    (the strategy has no `live_decision_position_size`) -- the audit's "unsized
    EXECUTE marked applied and forgotten" gap (v1 C2). A read-time anti-join
    between the decision and the open-positions table (any status), so there
    is no new table, no flag to keep in sync, and the list drains by itself
    once a strategy author sets a size and a later EXECUTE opens a position."""
    conn = backend._get_conn()
    rows = conn.execute(
        f"""SELECT d.* FROM {LIVE_DECISIONS_TABLE} d
            WHERE d.decision='EXECUTE' AND d.applied=1
              AND NOT EXISTS (
                  SELECT 1 FROM {LIVE_DECISION_OPEN_POSITIONS_TABLE} p
                  WHERE p.ticker=d.ticker AND p.strategy_id=d.strategy_id
                    AND p.trigger_id IS d.trigger_id)
            ORDER BY d.id DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [_row_to_decision(r) for r in rows]


def mark_decision_applied(backend: LiveDecisionBackend, decision_id: int) -> None:
    conn = backend._get_conn()
    conn.execute(
        f"UPDATE {LIVE_DECISIONS_TABLE} SET applied=1, applied_at=? WHERE id=?",
        (now_iso(), decision_id),
    )
    conn.commit()


# --- live_decision_open_positions ---------------------------------------
#
# The exit-mechanism fix (missing-pieces-of-system/new-theory-of-trading/
# system-wide-audit-and-design/04-synthesis-built-vs-missing-2026-09-28.md):
# this table is now the single source of truth LiveScheduler reads every
# cycle for a live_decision position's weight -- not the one-time
# `applied` flag above, which only marks that an EXECUTE has been
# converted into a row here.

def _row_to_open_position(row: Any) -> LiveDecisionOpenPosition:
    return LiveDecisionOpenPosition(
        id=row["id"],
        ticker=row["ticker"],
        strategy_id=row["strategy_id"],
        position_size=row["position_size"],
        opened_bar_ts=row["opened_bar_ts"],
        trigger_id=row["trigger_id"],
        status=row["status"],
        opened_at=row["opened_at"],
        last_reviewed_bar_ts=row["last_reviewed_bar_ts"],
        closed_at=row["closed_at"],
        closed_bar_ts=row["closed_bar_ts"],
        closed_reason=row["closed_reason"] or "",
        entry_price=row["entry_price"] if "entry_price" in row.keys() else None,
        exit_price=row["exit_price"] if "exit_price" in row.keys() else None,
        return_pct=row["return_pct"] if "return_pct" in row.keys() else None,
    )


def open_position(
    backend: LiveDecisionBackend,
    *,
    ticker: str,
    strategy_id: str,
    position_size: float,
    opened_bar_ts: int,
    trigger_id: str | None = None,
) -> LiveDecisionOpenPosition:
    """Called exactly once per EXECUTE decision that was actually sized
    (LiveScheduler._fetch_live_decision_weights) -- an unsized EXECUTE
    still marks the decision applied but never reaches here, since there
    is no real position to track without a real size."""
    conn = backend._get_conn()
    opened_at = now_iso()
    cur = conn.execute(
        f"""INSERT INTO {LIVE_DECISION_OPEN_POSITIONS_TABLE}
            (ticker, strategy_id, position_size, opened_bar_ts, trigger_id, status, opened_at)
            VALUES (?, ?, ?, ?, ?, 'open', ?)""",
        (ticker, strategy_id, position_size, opened_bar_ts, trigger_id, opened_at),
    )
    conn.commit()
    return LiveDecisionOpenPosition(
        id=cur.lastrowid, ticker=ticker, strategy_id=strategy_id,
        position_size=position_size, opened_bar_ts=opened_bar_ts,
        trigger_id=trigger_id, status="open", opened_at=opened_at,
    )


def list_open_positions(
    backend: LiveDecisionBackend, status: str = "open",
) -> list[LiveDecisionOpenPosition]:
    """Every position LiveScheduler must keep re-emitting a target_weight
    for (status="open") -- called every cycle, not just the cycle a
    position was opened, which is the actual bug fix here."""
    conn = backend._get_conn()
    rows = conn.execute(
        f"SELECT * FROM {LIVE_DECISION_OPEN_POSITIONS_TABLE} WHERE status=? ORDER BY id ASC",
        (status,),
    ).fetchall()
    return [_row_to_open_position(row) for row in rows]


def set_entry_price_if_missing(
    backend: LiveDecisionBackend, position_id: int, price: float,
) -> bool:
    """Record the reference price a rule-based stop measures against, ONCE.
    Never overwrites an existing value (the first priced cycle after the
    position opened is the entry reference; a later price is not the entry).
    Returns True only when a row was actually updated."""
    if not (price and price > 0):
        return False
    conn = backend._get_conn()
    cur = conn.execute(
        f"UPDATE {LIVE_DECISION_OPEN_POSITIONS_TABLE} SET entry_price=? "
        "WHERE id=? AND entry_price IS NULL AND status='open'",
        (float(price), position_id),
    )
    conn.commit()
    return cur.rowcount > 0


def mark_position_reviewed(backend: LiveDecisionBackend, position_id: int, bar_ts: int) -> None:
    conn = backend._get_conn()
    conn.execute(
        f"UPDATE {LIVE_DECISION_OPEN_POSITIONS_TABLE} SET last_reviewed_bar_ts=? WHERE id=?",
        (bar_ts, position_id),
    )
    conn.commit()


def _reference_return(position_size: float, entry_price: Any, exit_price: Any) -> float | None:
    """(exit / entry - 1), sign-flipped for a short; None unless both prices are finite and positive."""
    try:
        entry, exit_ = float(entry_price), float(exit_price)
    except (TypeError, ValueError):
        return None
    if not (entry > 0 and exit_ > 0) or entry != entry or exit_ != exit_ or entry == float("inf") or exit_ == float("inf"):
        return None
    raw = exit_ / entry - 1.0
    return -raw if position_size < 0 else raw


def close_position(
    backend: LiveDecisionBackend, position_id: int, *, reason: str, bar_ts: int,
    exit_price: float | None = None,
) -> None:
    """The actual exit: flips status to 'closed'. The *next* scheduler
    cycle then simply omits this position from `target_weights` -- and
    SignalTranslator's own existing "held but not in target_weights ->
    close to 0" rule (signal_translator.py's docstring) sells it, the
    same mechanism every other strategy exit already uses. No new sell
    logic is written for this -- reusing that rule is the point."""
    conn = backend._get_conn()
    exit_value: float | None = None
    return_pct: float | None = None
    if exit_price is not None:
        row = conn.execute(
            f"SELECT position_size, entry_price FROM {LIVE_DECISION_OPEN_POSITIONS_TABLE} WHERE id=?",
            (position_id,),
        ).fetchone()
        if row is not None:
            return_pct = _reference_return(row["position_size"], row["entry_price"], exit_price)
        try:
            candidate = float(exit_price)
            exit_value = candidate if candidate > 0 and candidate == candidate and candidate != float("inf") else None
        except (TypeError, ValueError):
            exit_value = None
    conn.execute(
        f"""UPDATE {LIVE_DECISION_OPEN_POSITIONS_TABLE}
            SET status='closed', closed_at=?, closed_bar_ts=?, closed_reason=?,
                last_reviewed_bar_ts=?, exit_price=?, return_pct=?
            WHERE id=?""",
        (now_iso(), bar_ts, reason, bar_ts, exit_value, return_pct, position_id),
    )
    conn.commit()


# --- live_snapshots (append-only, "present-data" recording, item #5) ---

def _row_to_snapshot(row: Any) -> LiveSnapshotRecord:
    return LiveSnapshotRecord(
        id=row["id"],
        symbol=row["symbol"],
        angle_name=row["angle_name"],
        granularity=row["granularity"],
        computed_at=row["computed_at"],
        snapshot_data=snapshot_from_json(row["snapshot_data"]),
    )


def record_live_snapshot(
    backend: LiveDecisionBackend,
    *,
    symbol: str,
    angle_name: str,
    granularity: str,
    snapshot_data: dict[str, Any],
    computed_at: str | None = None,
) -> LiveSnapshotRecord:
    """One new row per real computation -- an append-only log mirroring
    `RunLog`'s own shape, not an upserted "current" row, so a history of
    what the live snapshot looked like at each past computation stays
    queryable, the same way `RunLog` itself is a log, not a cache.
    `computed_at` defaults to real wall-clock now -- callers pass an
    explicit value only in tests that need a fixed timestamp."""
    computed_at = computed_at or now_iso()
    conn = backend._get_conn()
    cur = conn.execute(
        f"""INSERT INTO {LIVE_SNAPSHOTS_TABLE}
            (symbol, angle_name, granularity, computed_at, snapshot_data)
            VALUES (?, ?, ?, ?, ?)""",
        (symbol, angle_name, granularity, computed_at, snapshot_to_json(snapshot_data)),
    )
    conn.commit()
    return LiveSnapshotRecord(
        id=cur.lastrowid, symbol=symbol, angle_name=angle_name, granularity=granularity,
        computed_at=computed_at, snapshot_data=snapshot_data,
    )


def get_latest_snapshot(
    backend: LiveDecisionBackend, symbol: str, angle_name: str,
) -> LiveSnapshotRecord | None:
    conn = backend._get_conn()
    row = conn.execute(
        f"""SELECT * FROM {LIVE_SNAPSHOTS_TABLE} WHERE symbol=? AND angle_name=?
            ORDER BY id DESC LIMIT 1""",
        (symbol, angle_name),
    ).fetchone()
    if row is None:
        return None
    return _row_to_snapshot(row)


def list_snapshot_angle_names(backend: LiveDecisionBackend, symbol: str) -> list[str]:
    """Every angle_name ever recorded for this symbol -- lets a reader
    enumerate what's actually available rather than guessing names."""
    conn = backend._get_conn()
    rows = conn.execute(
        f"SELECT DISTINCT angle_name FROM {LIVE_SNAPSHOTS_TABLE} WHERE symbol=?",
        (symbol,),
    ).fetchall()
    return [r["angle_name"] for r in rows]


def list_snapshots(
    backend: LiveDecisionBackend, symbol: str, angle_name: str, limit: int = 50,
) -> list[LiveSnapshotRecord]:
    """History for one (symbol, angle_name), most recent first -- the
    "present-data" analogue of `RunLog.get_runs()`."""
    conn = backend._get_conn()
    rows = conn.execute(
        f"""SELECT * FROM {LIVE_SNAPSHOTS_TABLE} WHERE symbol=? AND angle_name=?
            ORDER BY id DESC LIMIT ?""",
        (symbol, angle_name, limit),
    ).fetchall()
    return [_row_to_snapshot(row) for row in rows]


def staleness_seconds(computed_at: str) -> float | None:
    """Computed fresh at read time from `computed_at` -- never stored,
    same "coverage view computed fresh, never cached" rule
    `ticker_coverage.py`'s own `_days_stale()` already established for a
    different table. `None` for an unparseable timestamp (absence of
    evidence, not zero staleness), matching that function's own contract."""
    try:
        dt = datetime.fromisoformat(computed_at)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds()
