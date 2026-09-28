"""Move evidence store -- Track 2's own side of item #10 (system-wide-
audit-and-design/02-open-questions-strategy-and-simulation.md,
"cross-track disagreement as its own signal").

Sibling of `signal_evidence_store.py` (Track 1's trigger history), not a
merge into it: this table records a real price move (2xATR(14),
`vinu-live`'s `detect_move()`) *unconditionally*, whether or not any
strategy's must-condition happened to fire in that same window --
that's the whole point of item #10's `track2_only` case (a real move
with no strategy watching for it), which is structurally impossible to
capture if this only ever wrote alongside a Track 1 trigger.

Only real detections are stored (`move_detected=True`), same "record
real events, not every idle bar" discipline `signal_triggers` already
uses -- one row per bar for every watched ticker forever would be pure
noise, not evidence.

`window_time`/`window_seconds` (not just `bar_ts`) exist so a
reconciliation query can compare this row's window directly against
`SignalEvidenceStore.trigger_time` (an ISO8601 string) without either
store needing to know the other's timeframe-to-seconds mapping --
`window_seconds` is recorded by the caller (`vinu-live`'s poller, which
already knows its own timeframe) at write time, not re-derived here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS move_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol              TEXT NOT NULL,
    bar_ts              INTEGER NOT NULL,
    window_time         TEXT NOT NULL,
    window_seconds      INTEGER NOT NULL,
    granularity         TEXT NOT NULL,
    atr                 REAL NOT NULL,
    price_move          REAL NOT NULL,
    move_threshold      REAL NOT NULL,
    direction           TEXT NOT NULL,
    created_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_move_events_symbol ON move_events(symbol);
CREATE INDEX IF NOT EXISTS idx_move_events_window_time ON move_events(window_time);
"""


class MoveEvidenceStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def record_move_event(
        self,
        symbol: str,
        *,
        bar_ts: int,
        window_seconds: int,
        granularity: str,
        atr: float,
        price_move: float,
        move_threshold: float,
        direction: str,
    ) -> int:
        conn = self._get_conn()
        window_time = datetime.fromtimestamp(bar_ts, tz=timezone.utc).isoformat()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO move_events
               (symbol, bar_ts, window_time, window_seconds, granularity,
                atr, price_move, move_threshold, direction, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (symbol, bar_ts, window_time, window_seconds, granularity,
             atr, price_move, move_threshold, direction, now),
        )
        conn.commit()
        return int(cur.lastrowid)

    def list_move_events(self, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        query = "SELECT * FROM move_events WHERE 1=1"
        params: list[Any] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        query += " ORDER BY window_time DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
