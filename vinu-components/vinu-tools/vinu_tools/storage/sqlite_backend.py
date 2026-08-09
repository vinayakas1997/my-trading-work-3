"""SQLite storage backend for feature request registry."""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from vinu_tools.storage.models import (
    STATUS_DELETED,
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_RUNNING,
    FeatureRequest,
    SubmitRequest,
    slugify_title,
    utc_now_iso,
)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS feature_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    slug TEXT NOT NULL,
    symbols TEXT NOT NULL,
    from_ts INTEGER NOT NULL,
    to_ts INTEGER NOT NULL,
    interval TEXT NOT NULL DEFAULT '1d',
    preset TEXT,
    features TEXT NOT NULL,
    conditions TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    file_path TEXT,
    error_message TEXT,
    request_hash TEXT NOT NULL,
    row_count INTEGER NOT NULL DEFAULT 0,
    ml_model TEXT,
    ml_label TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_feature_requests_status ON feature_requests(status);
CREATE INDEX IF NOT EXISTS idx_feature_requests_title ON feature_requests(title);
CREATE INDEX IF NOT EXISTS idx_feature_requests_hash ON feature_requests(request_hash);
"""


class SqliteBackend:
    """Real fix: `close()` used to close only the calling thread's own
    connection. `worker/runner.py`'s `FeatureWorker.process_pending()`
    dispatches concurrent jobs onto a fresh `ThreadPoolExecutor` on every
    call, and each of those worker threads opens its own connection via
    `_get_conn()` -- those connections were never closed by anyone, relying
    on `__del__` at GC time instead. Same bug class, same fix, as
    `vinu_infra.sqlite.SQLiteBackend`: track every connection opened by
    every thread, and a generation counter so any thread whose connection
    was closed out from under it transparently reopens on next use."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._all_conns: list[sqlite3.Connection] = []
        self._all_conns_lock = threading.Lock()
        self._generation = 0
        self._init_connection()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        gen = getattr(self._local, "gen", -1)
        if conn is None or gen != self._generation:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            self._migrate(conn)
            self._local.conn = conn
            self._local.gen = self._generation
            with self._all_conns_lock:
                self._all_conns.append(conn)
        return conn

    _SCHEMA_VERSION = 1

    def _migrate(self, conn: sqlite3.Connection) -> None:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            for col in ("ml_model", "ml_label"):
                try:
                    conn.execute(f"ALTER TABLE feature_requests ADD COLUMN {col} TEXT")
                except sqlite3.OperationalError:
                    pass
            conn.execute("PRAGMA user_version=1")
        conn.commit()

    def _init_connection(self) -> None:
        _ = self._get_conn()

    def close(self) -> None:
        with self._all_conns_lock:
            conns, self._all_conns = self._all_conns, []
            self._generation += 1
        for conn in conns:
            # A connection opened by another (possibly now-dead) thread
            # can't be close()'d from here -- sqlite3 raises
            # ProgrammingError for cross-thread use, close() included.
            # The generation bump above already makes that thread reopen
            # transparently next use; the old connection object becomes
            # unreachable and is closed by Python's GC finalizer instead.
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                pass
        self._local.conn = None

    def __enter__(self) -> SqliteBackend:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def insert_request(
        self,
        req: SubmitRequest,
        *,
        request_hash: str,
        features: list[str],
    ) -> FeatureRequest:
        conn = self._get_conn()
        now = utc_now_iso()
        slug = slugify_title(req.title)
        cur = conn.execute(
            """
            INSERT INTO feature_requests (
                title, slug, symbols, from_ts, to_ts, interval, preset, features,
                conditions, status, request_hash, ml_model, ml_label, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.title,
                slug,
                json.dumps(req.symbols),
                req.from_ts,
                req.to_ts,
                req.interval,
                req.preset,
                json.dumps(features),
                req.conditions,
                STATUS_PENDING,
                request_hash,
                req.ml_model,
                req.ml_label,
                now,
                now,
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        result = self.get_request(row_id)
        assert result is not None
        return result

    def get_request(self, request_id: int) -> FeatureRequest | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM feature_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return FeatureRequest.from_row(dict(row))

    def get_latest_by_title(self, title: str) -> FeatureRequest | None:
        conn = self._get_conn()
        row = conn.execute(
            """
            SELECT * FROM feature_requests
            WHERE title = ? AND status != ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (title, STATUS_DELETED),
        ).fetchone()
        if row is None:
            return None
        return FeatureRequest.from_row(dict(row))

    def get_by_hash(self, request_hash: str, *, status: str | None = None) -> FeatureRequest | None:
        conn = self._get_conn()
        if status:
            row = conn.execute(
                """
                SELECT * FROM feature_requests
                WHERE request_hash = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (request_hash, status),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT * FROM feature_requests
                WHERE request_hash = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (request_hash,),
            ).fetchone()
        if row is None:
            return None
        return FeatureRequest.from_row(dict(row))

    _ALLOWED_FILTERS = frozenset({"status", "title"})

    def list_requests(
        self,
        *,
        status: str | None = None,
        title: str | None = None,
        limit: int = 100,
    ) -> list[FeatureRequest]:
        conn = self._get_conn()
        params: list[Any] = [STATUS_DELETED]
        conditions: list[str] = ["status != ?"]
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if title is not None:
            conditions.append("title = ?")
            params.append(title)
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT * FROM feature_requests
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [FeatureRequest.from_row(dict(r)) for r in rows]

    def claim_next_pending(self) -> FeatureRequest | None:
        conn = self._get_conn()
        now = utc_now_iso()
        row = conn.execute(
            """
            UPDATE feature_requests
            SET status = ?, updated_at = ?, error_message = NULL
            WHERE id = (
                SELECT id FROM feature_requests
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
            )
            RETURNING *
            """,
            (STATUS_RUNNING, now, STATUS_PENDING),
        ).fetchone()
        conn.commit()
        if row is None:
            return None
        return FeatureRequest.from_row(dict(row))

    def mark_running(self, request_id: int) -> FeatureRequest | None:
        conn = self._get_conn()
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE feature_requests
            SET status = ?, updated_at = ?, error_message = NULL
            WHERE id = ? AND status = ?
            """,
            (STATUS_RUNNING, now, request_id, STATUS_PENDING),
        )
        conn.commit()
        req = self.get_request(request_id)
        return req if req and req.status == STATUS_RUNNING else None

    def mark_done(
        self,
        request_id: int,
        *,
        file_path: str,
        row_count: int,
    ) -> FeatureRequest | None:
        conn = self._get_conn()
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE feature_requests
            SET status = ?, file_path = ?, row_count = ?, updated_at = ?, error_message = NULL
            WHERE id = ?
            """,
            (STATUS_DONE, file_path, row_count, now, request_id),
        )
        conn.commit()
        return self.get_request(request_id)

    def mark_failed(self, request_id: int, *, error_message: str) -> FeatureRequest | None:
        conn = self._get_conn()
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE feature_requests
            SET status = ?, error_message = ?, updated_at = ?
            WHERE id = ?
            """,
            (STATUS_FAILED, error_message, now, request_id),
        )
        conn.commit()
        return self.get_request(request_id)

    def mark_deleted(self, request_id: int) -> FeatureRequest | None:
        conn = self._get_conn()
        now = utc_now_iso()
        conn.execute(
            """
            UPDATE feature_requests
            SET status = ?, file_path = NULL, updated_at = ?
            WHERE id = ?
            """,
            (STATUS_DELETED, now, request_id),
        )
        conn.commit()
        return self.get_request(request_id)

    def health_info(self) -> dict[str, Any]:
        conn = self._get_conn()
        counts = conn.execute(
            """
            SELECT status, COUNT(*) AS cnt
            FROM feature_requests
            WHERE status != ?
            GROUP BY status
            """,
            (STATUS_DELETED,),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM feature_requests"
        ).fetchone()[0]
        return {
            "db_path": str(self.db_path),
            "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "total_request_count": total,
            "status_counts": {r["status"]: r["cnt"] for r in counts},
        }
