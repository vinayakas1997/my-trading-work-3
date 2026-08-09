"""Ephemeral in-flight batch tracker for "run every angle for these
tickers" jobs -- deliberately separate from meta.py's RunLog.

RunLog is a permanent, append-only audit of *completed* runs (used to
resolve "what's the latest run for symbol+angle+granularity+tier").
AngleRunStatus is the opposite: a live status board for a batch that's
*currently* in progress -- every (symbol, angle) job gets registered up
front so there's full visibility into the whole planned batch before any
work starts, status flips as each job runs/succeeds/fails, failures are
retried, and once every job in the batch is 'ok' the batch's rows are
deleted -- this table only ever holds in-flight or stuck work, never a
permanent history (RunLog already is that).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from vinu_infra.sqlite import SQLiteBackend

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS angle_run_status (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    angle_name   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error   TEXT,
    started_at   TEXT,
    heartbeat_at TEXT,
    UNIQUE(batch_id, symbol, angle_name)
);
CREATE INDEX IF NOT EXISTS idx_angle_run_status_batch ON angle_run_status(batch_id);
"""


class AngleRunStatus(SQLiteBackend):
    SCHEMA = SCHEMA_SQL

    def register_batch(
        self, batch_id: str, jobs: list[tuple[str, str]], *, max_attempts: int = 3
    ) -> None:
        """Registers every (symbol, angle_name) job as 'pending' up front --
        full visibility into the whole planned batch before any work
        starts, not just whatever's currently running."""
        conn = self._get_conn()
        for symbol, angle_name in jobs:
            conn.execute(
                """INSERT OR IGNORE INTO angle_run_status
                   (batch_id, symbol, angle_name, status, max_attempts)
                   VALUES (?, ?, ?, 'pending', ?)""",
                (batch_id, symbol, angle_name, max_attempts),
            )
        conn.commit()

    def mark_running(self, batch_id: str, symbol: str, angle_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """UPDATE angle_run_status
               SET status='running', started_at=COALESCE(started_at, ?),
                   heartbeat_at=?, attempts=attempts+1
               WHERE batch_id=? AND symbol=? AND angle_name=?""",
            (now, now, batch_id, symbol, angle_name),
        )
        conn.commit()

    def heartbeat(self, batch_id: str, symbol: str, angle_name: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE angle_run_status SET heartbeat_at=? WHERE batch_id=? AND symbol=? AND angle_name=?",
            (now, batch_id, symbol, angle_name),
        )
        conn.commit()

    def mark_ok(self, batch_id: str, symbol: str, angle_name: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE angle_run_status SET status='ok', last_error=NULL WHERE batch_id=? AND symbol=? AND angle_name=?",
            (batch_id, symbol, angle_name),
        )
        conn.commit()

    def mark_failed(self, batch_id: str, symbol: str, angle_name: str, error: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE angle_run_status SET status='failed', last_error=? WHERE batch_id=? AND symbol=? AND angle_name=?",
            (error, batch_id, symbol, angle_name),
        )
        conn.commit()

    def get_batch_status(self, batch_id: str) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM angle_run_status WHERE batch_id=? ORDER BY symbol, angle_name", (batch_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def is_batch_complete(self, batch_id: str) -> bool:
        """True iff the batch has at least one row and every row is 'ok'."""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT COUNT(*) AS total, SUM(CASE WHEN status='ok' THEN 1 ELSE 0 END) AS done
               FROM angle_run_status WHERE batch_id=?""",
            (batch_id,),
        ).fetchone()
        total = row["total"] or 0
        done = row["done"] or 0
        return total > 0 and total == done

    def delete_batch(self, batch_id: str) -> int:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM angle_run_status WHERE batch_id=?", (batch_id,))
        conn.commit()
        return cursor.rowcount

    def stale_running_rows(self, older_than_seconds: int = 300) -> list[dict[str, Any]]:
        """Rows stuck in 'running' with no heartbeat in `older_than_seconds`
        -- the crash-recovery signal: a process that died mid-job leaves a
        row here forever otherwise, indistinguishable from real in-progress
        work without this check. Known limitation: heartbeat is only set
        when a job starts (mark_running), not updated *during* a single
        long-running synchronous call -- `older_than_seconds` needs to stay
        generously above the slowest real angle's own runtime, or a
        legitimately-still-running job gets flagged as stale."""
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)).isoformat()
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM angle_run_status WHERE status='running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def run_batch(
    tracker: AngleRunStatus,
    batch_id: str,
    jobs: list[tuple[str, str, Callable[[], Any]]],
    *,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Registers every job, runs each with retry + live status tracking,
    deletes the batch's rows once every job succeeds. `jobs` is
    (symbol, angle_name, work_fn) -- work_fn is a zero-arg callable the
    caller builds (e.g. `lambda: run_timer_timerxl_backtest("AAPL", "1D", bars)`),
    same dependency-injection shape as the walk-forward harness's step_fn.

    Returns {"results": {"SYMBOL:angle": <work_fn's return value>},
    "errors": {"SYMBOL:angle": "<error string>"}, "ok": bool}. A job that
    exhausts max_attempts lands in `errors` and its row stays 'failed'
    (not deleted) -- the batch's rows are only cleared when every single
    one succeeded.
    """
    tracker.register_batch(batch_id, [(s, a) for s, a, _ in jobs], max_attempts=max_attempts)

    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for symbol, angle_name, work_fn in jobs:
        key = f"{symbol}:{angle_name}"
        last_error = ""
        for attempt in range(1, max_attempts + 1):
            tracker.mark_running(batch_id, symbol, angle_name)
            try:
                results[key] = work_fn()
                tracker.mark_ok(batch_id, symbol, angle_name)
                break
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt >= max_attempts:
                    tracker.mark_failed(batch_id, symbol, angle_name, last_error)
                    errors[key] = last_error

    if tracker.is_batch_complete(batch_id):
        tracker.delete_batch(batch_id)

    return {"results": results, "errors": errors, "ok": not errors}
