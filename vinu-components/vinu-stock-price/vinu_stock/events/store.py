"""Local SQLite store for the event-risk calendar.

One table, `events`, holding upcoming earnings and macro-economic events; a
`events_meta` key/value table tracking when each `kind` was last refreshed so
the poller can throttle itself to one upstream pull per day. Macro events apply
to every symbol and are stored under the sentinel symbol `*MACRO*`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

MACRO_SYMBOL = "*MACRO*"


@dataclass(frozen=True)
class EventRecord:
    symbol: str
    kind: str  # 'earnings' | 'economic'
    event_ts: float  # UTC epoch seconds
    title: str = ""
    severity: int = 1  # 1 = normal, 2 = high-impact

    def as_row(self, pulled_at: float) -> dict[str, Any]:
        return {
            "symbol": self.symbol.strip().upper(),
            "kind": self.kind,
            "event_ts": float(self.event_ts),
            "title": self.title or "",
            "severity": int(self.severity),
            "pulled_at": float(pulled_at),
        }


class EventsStore(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS events (
        symbol     TEXT    NOT NULL,
        kind       TEXT    NOT NULL,
        event_ts   REAL    NOT NULL,
        title      TEXT    NOT NULL DEFAULT '',
        severity   INTEGER NOT NULL DEFAULT 1,
        pulled_at  REAL    NOT NULL,
        PRIMARY KEY (symbol, kind, event_ts, title)
    );
    CREATE INDEX IF NOT EXISTS idx_events_symbol_ts ON events (symbol, event_ts);
    CREATE TABLE IF NOT EXISTS events_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    -- Permanent history of every event this store has ever seen --
    -- `events` above is deliberately just "the current lookahead
    -- snapshot" (replace_kind() deletes a kind's rows every pull), so by
    -- the time a trade that overlapped an event actually closes, the
    -- event row is very likely already gone (25-A-Y-details/
    -- 03-execution-money-flow.md, analysis Y). This table is the new
    -- writer that closes that gap: rows are copied here right before
    -- `events` deletes them, and never removed afterward.
    CREATE TABLE IF NOT EXISTS events_archive (
        symbol      TEXT    NOT NULL,
        kind        TEXT    NOT NULL,
        event_ts    REAL    NOT NULL,
        title       TEXT    NOT NULL DEFAULT '',
        severity    INTEGER NOT NULL DEFAULT 1,
        pulled_at   REAL    NOT NULL,
        archived_at REAL    NOT NULL,
        PRIMARY KEY (symbol, kind, event_ts, title)
    );
    CREATE INDEX IF NOT EXISTS idx_events_archive_symbol_ts ON events_archive (symbol, event_ts);
    """
    SCHEMA_VERSION = 1

    # -- refresh bookkeeping -------------------------------------------------

    def get_last_pull(self, kind: str) -> float:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM events_meta WHERE key = ?", (f"last_pull:{kind}",)
        ).fetchone()
        if not row:
            return 0.0
        try:
            return float(row["value"])
        except (TypeError, ValueError):
            return 0.0

    def set_last_pull(self, kind: str, ts: float | None = None) -> None:
        ts = time.time() if ts is None else float(ts)
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO events_meta (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            (f"last_pull:{kind}", str(ts)),
        )
        conn.commit()

    # -- writes -----------------------------------------------------------------

    def replace_kind(self, kind: str, records: list[EventRecord]) -> int:
        """Atomically swap every row of `kind` for `records`. A calendar pull
        is a full snapshot of the lookahead window, so a stale row (event
        cancelled / rescheduled) must not survive -- delete-then-insert, not
        upsert. Every row about to be deleted is archived into
        `events_archive` first (INSERT OR IGNORE: a still-upcoming event
        seen across several pulls in a row is already archived from its
        first pull, and must not be re-inserted with a fresher, wrong
        `archived_at`)."""
        pulled_at = time.time()
        rows = [r.as_row(pulled_at) for r in records if r.kind == kind]
        conn = self._get_conn()
        conn.execute(
            "INSERT OR IGNORE INTO events_archive "
            "(symbol, kind, event_ts, title, severity, pulled_at, archived_at) "
            "SELECT symbol, kind, event_ts, title, severity, pulled_at, ? FROM events WHERE kind = ?",
            (time.time(), kind),
        )
        conn.execute("DELETE FROM events WHERE kind = ?", (kind,))
        if rows:
            conn.executemany(
                "INSERT INTO events (symbol, kind, event_ts, title, severity, pulled_at) "
                "VALUES (:symbol, :kind, :event_ts, :title, :severity, :pulled_at) "
                "ON CONFLICT (symbol, kind, event_ts, title) DO UPDATE SET "
                "severity = excluded.severity, pulled_at = excluded.pulled_at",
                rows,
            )
        conn.commit()
        return len(rows)

    # -- reads ----------------------------------------------------------------

    def upcoming(self, symbol: str, from_ts: float, to_ts: float) -> list[dict[str, Any]]:
        """Events for `symbol` (plus every macro event) with
        `from_ts <= event_ts <= to_ts`, soonest first."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT symbol, kind, event_ts, title, severity FROM events "
            "WHERE (symbol = ? OR symbol = ?) AND event_ts >= ? AND event_ts <= ? "
            "ORDER BY event_ts ASC",
            (symbol.strip().upper(), MACRO_SYMBOL, float(from_ts), float(to_ts)),
        ).fetchall()
        return [dict(r) for r in rows]

    def count(self) -> int:
        conn = self._get_conn()
        return int(conn.execute("SELECT COUNT(*) FROM events").fetchone()[0])

    def archived_overlapping(self, symbol: str, from_ts: float, to_ts: float) -> list[dict[str, Any]]:
        """Same shape as `upcoming()` but reads the permanent archive
        instead of the current lookahead snapshot -- for a closed trade
        whose `[entry_ts, exit_ts]` window is in the past, this is the
        only place that overlap can still be checked (analysis Y)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT symbol, kind, event_ts, title, severity FROM events_archive "
            "WHERE (symbol = ? OR symbol = ?) AND event_ts >= ? AND event_ts <= ? "
            "ORDER BY event_ts ASC",
            (symbol.strip().upper(), MACRO_SYMBOL, float(from_ts), float(to_ts)),
        ).fetchall()
        return [dict(r) for r in rows]
