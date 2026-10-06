"""The two tables: `llm_queue` (hot: queued, running, or done but not yet handed to the caller) and `llm_history`
(everything that finished, kept for reports). A row moves from one to the other in a single transaction, so a call is
never lost and never stored twice, and the table the worker scans stays small.

A row leaves the queue only when it was DELIVERED to the caller, or it can never be delivered (expired, abandoned,
failed for good, cancelled because the caller hung up). It is not deleted the moment the answer exists: a caller that
crashes while waiting would otherwise lose an answer that was already paid for.

The API key is never stored: a row carries `api_key_ref`, the NAME of a secret file the worker reads at call time.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from vinu_infra.db import enable_wal

COLUMNS = [
    "id", "provider", "base_url", "model", "max_tokens", "temperature", "extra_json", "request_json", "tools_json",
    "api_key_ref", "priority", "caller", "purpose", "ticker", "run_id", "status", "enqueued_at", "started_at",
    "finished_at", "deadline_at", "timeout_sec", "attempts", "max_attempts", "next_retry_at", "error",
    "response_json", "prompt_tokens", "completion_tokens", "wait_ms", "run_ms", "worker_id", "dedupe_key",
    "delivered_at",
]
_DDL_COLUMNS = """
    id TEXT PRIMARY KEY, provider TEXT NOT NULL, base_url TEXT NOT NULL, model TEXT NOT NULL,
    max_tokens INTEGER NOT NULL, temperature REAL, extra_json TEXT, request_json TEXT NOT NULL, tools_json TEXT,
    api_key_ref TEXT, priority INTEGER NOT NULL, caller TEXT NOT NULL, purpose TEXT NOT NULL, ticker TEXT, run_id TEXT,
    status TEXT NOT NULL, enqueued_at REAL NOT NULL, started_at REAL, finished_at REAL, deadline_at REAL NOT NULL,
    timeout_sec REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
    next_retry_at REAL, error TEXT, response_json TEXT, prompt_tokens INTEGER, completion_tokens INTEGER,
    wait_ms INTEGER, run_ms INTEGER, worker_id TEXT, dedupe_key TEXT, delivered_at REAL
"""
# statuses: queued -> running -> done | failed ; plus expired, cancelled (only ever seen in history)
LIVE_STATUSES = ("queued", "running", "done", "failed")


class QueueStore:
    def __init__(self, db_path: str | Path) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False, isolation_level=None, timeout=30)
        self._conn.row_factory = sqlite3.Row
        enable_wal(self._conn)
        self._conn.execute("PRAGMA busy_timeout=30000")
        self._conn.execute(f"CREATE TABLE IF NOT EXISTS llm_queue ({_DDL_COLUMNS})")
        self._conn.execute(
            f"CREATE TABLE IF NOT EXISTS llm_history ({_DDL_COLUMNS}, archive_reason TEXT, archived_at REAL)"
        )
        self._conn.execute("CREATE INDEX IF NOT EXISTS ix_queue_pick ON llm_queue(status, priority, enqueued_at)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS ix_queue_dedupe ON llm_queue(dedupe_key, status)")
        self._conn.execute("CREATE INDEX IF NOT EXISTS ix_hist_when ON llm_history(archived_at)")

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---- writing -------------------------------------------------------------------------------------------------

    def enqueue(self, row: dict[str, Any], *, now: float | None = None) -> tuple[str, bool]:
        """(id, shared). An identical request already queued or running is shared, not queued twice."""
        now = time.time() if now is None else now
        with self._lock:
            if row.get("dedupe_key"):
                hit = self._conn.execute(
                    "SELECT id FROM llm_queue WHERE dedupe_key=? AND status IN ('queued','running') LIMIT 1",
                    (row["dedupe_key"],),
                ).fetchone()
                if hit:
                    return hit["id"], True
            data = {c: row.get(c) for c in COLUMNS}
            data["id"] = data["id"] or uuid.uuid4().hex
            data["status"] = "queued"
            data["enqueued_at"] = now
            data["attempts"] = 0
            marks = ",".join("?" for _ in COLUMNS)
            self._conn.execute(
                f"INSERT INTO llm_queue ({','.join(COLUMNS)}) VALUES ({marks})", [data[c] for c in COLUMNS]
            )
            return data["id"], False

    def claim_next(self, worker_id: str, *, age_step_sec: float, now: float | None = None) -> sqlite3.Row | None:
        """Pick the most urgent queued row and mark it running, in one step so two workers can never take the same row.

        Urgency is the priority number minus one level per `age_step_sec` waited (never below 1), so a priority-5 call
        cannot starve behind an endless stream of priority-1 calls. Ties go to whoever came first."""
        now = time.time() if now is None else now
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute(
                    """SELECT * FROM llm_queue WHERE status='queued' AND (next_retry_at IS NULL OR next_retry_at<=?)
                       ORDER BY MAX(1, priority - CAST((? - enqueued_at) / ? AS INTEGER)), enqueued_at LIMIT 1""",
                    (now, now, age_step_sec),
                ).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return None
                self._conn.execute(
                    "UPDATE llm_queue SET status='running', started_at=?, worker_id=?, attempts=attempts+1, "
                    "wait_ms=COALESCE(wait_ms, CAST((?-enqueued_at)*1000 AS INTEGER)) WHERE id=?",
                    (now, worker_id, now, row["id"]),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
            return self.get(row["id"])

    def finish_ok(self, row_id: str, response_json: str, prompt_tokens: int | None, completion_tokens: int | None,
                  *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._conn.execute(
                "UPDATE llm_queue SET status='done', finished_at=?, response_json=?, prompt_tokens=?, "
                "completion_tokens=?, error=NULL, run_ms=CAST((?-started_at)*1000 AS INTEGER) WHERE id=?",
                (now, response_json, prompt_tokens, completion_tokens, now, row_id),
            )

    def finish_failed(self, row_id: str, error: str, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._conn.execute(
                "UPDATE llm_queue SET status='failed', finished_at=?, error=?, "
                "run_ms=CAST((?-started_at)*1000 AS INTEGER) WHERE id=?",
                (now, error[:2000], now, row_id),
            )

    def retry_later(self, row_id: str, error: str, delay_sec: float, *, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self._lock:
            self._conn.execute(
                "UPDATE llm_queue SET status='queued', next_retry_at=?, error=?, started_at=NULL WHERE id=?",
                (now + delay_sec, error[:2000], row_id),
            )

    # ---- leaving the queue ---------------------------------------------------------------------------------------

    def archive(self, row_id: str, reason: str, *, now: float | None = None) -> bool:
        """Move one row to history atomically. `reason` is delivered | undelivered | expired | cancelled | failed."""
        now = time.time() if now is None else now
        cols = ",".join(COLUMNS)
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT status FROM llm_queue WHERE id=?", (row_id,)).fetchone()
                if row is None:
                    self._conn.execute("COMMIT")
                    return False
                self._conn.execute(
                    f"INSERT OR REPLACE INTO llm_history ({cols}, archive_reason, archived_at) "
                    f"SELECT {cols}, ?, ? FROM llm_queue WHERE id=?",
                    (reason, now, row_id),
                )
                if reason == "delivered":
                    self._conn.execute("UPDATE llm_history SET delivered_at=? WHERE id=?", (now, row_id))
                if reason in ("expired", "cancelled"):
                    self._conn.execute(
                        "UPDATE llm_history SET status=?, finished_at=COALESCE(finished_at, ?) WHERE id=?",
                        (reason, now, row_id),
                    )
                self._conn.execute("DELETE FROM llm_queue WHERE id=?", (row_id,))
                self._conn.execute("COMMIT")
                return True
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

    def sweep(self, *, running_grace_sec: float = 60.0, undelivered_after_sec: float = 600.0,
              now: float | None = None) -> dict[str, list[str]]:
        """Housekeeping: nothing may sit in the queue forever.

        queued past its deadline -> history `expired`; done/failed and nobody collected it -> `undelivered`;
        running far past its own timeout (a worker that died) -> back to queued so another attempt can run."""
        now = time.time() if now is None else now
        out: dict[str, list[str]] = {"expired": [], "undelivered": [], "requeued": []}
        with self._lock:
            for r in self._conn.execute(
                "SELECT id FROM llm_queue WHERE status='queued' AND deadline_at<?", (now,)
            ).fetchall():
                out["expired"].append(r["id"])
            for r in self._conn.execute(
                "SELECT id FROM llm_queue WHERE status IN ('done','failed') AND finished_at<?",
                (now - undelivered_after_sec,),
            ).fetchall():
                out["undelivered"].append(r["id"])
            for r in self._conn.execute(
                "SELECT id FROM llm_queue WHERE status='running' AND started_at + timeout_sec + ? < ?",
                (running_grace_sec, now),
            ).fetchall():
                out["requeued"].append(r["id"])
        for rid in out["expired"]:
            self.archive(rid, "expired", now=now)
        for rid in out["undelivered"]:
            self.archive(rid, "undelivered", now=now)
        with self._lock:
            for rid in out["requeued"]:
                self._conn.execute(
                    "UPDATE llm_queue SET status='queued', started_at=NULL, error='worker lost; requeued' WHERE id=?",
                    (rid,),
                )
        return out

    def trim_history(self, older_than_days: float, *, now: float | None = None) -> int:
        """Drop the big JSON (prompt, reply) from old history rows; keep who, why, when, tokens and timings."""
        now = time.time() if now is None else now
        with self._lock:
            cur = self._conn.execute(
                "UPDATE llm_history SET request_json='', response_json=NULL, tools_json=NULL "
                "WHERE archived_at<? AND request_json<>''",
                (now - older_than_days * 86400,),
            )
            return cur.rowcount

    # ---- reading -------------------------------------------------------------------------------------------------

    def get(self, row_id: str) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute("SELECT * FROM llm_queue WHERE id=?", (row_id,)).fetchone()

    def stats(self, *, now: float | None = None) -> dict[str, Any]:
        now = time.time() if now is None else now
        with self._lock:
            by_status = {r["status"]: r["n"] for r in self._conn.execute(
                "SELECT status, COUNT(*) n FROM llm_queue GROUP BY status")}
            waiting = [dict(r) for r in self._conn.execute(
                "SELECT id, priority, caller, purpose, ticker, ROUND(?-enqueued_at,1) AS waited_sec "
                "FROM llm_queue WHERE status='queued' ORDER BY priority, enqueued_at LIMIT 50", (now,))]
            running = [dict(r) for r in self._conn.execute(
                "SELECT id, priority, caller, purpose, ticker, ROUND(?-started_at,1) AS running_sec "
                "FROM llm_queue WHERE status='running'", (now,))]
            hist = self._conn.execute("SELECT COUNT(*) n FROM llm_history").fetchone()["n"]
        return {
            "queue": by_status, "waiting": waiting, "running": running, "history_rows": hist,
            "longest_wait_sec": max((w["waited_sec"] for w in waiting), default=0.0),
        }

    def history(self, limit: int = 100, caller: str | None = None) -> list[dict[str, Any]]:
        sql = ("SELECT id, caller, purpose, priority, ticker, run_id, model, status, archive_reason, attempts, "
               "prompt_tokens, completion_tokens, wait_ms, run_ms, error, enqueued_at, archived_at FROM llm_history")
        args: list[Any] = []
        if caller:
            sql += " WHERE caller=?"
            args.append(caller)
        sql += " ORDER BY archived_at DESC LIMIT ?"
        args.append(int(limit))
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, args)]


def dedupe_key(model: str, request: dict[str, Any]) -> str:
    """Same model + same messages + same settings => same call."""
    import hashlib
    return hashlib.sha256(json.dumps([model, request], sort_keys=True, default=str).encode()).hexdigest()
