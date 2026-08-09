"""Shared SQLite backend with thread-local connections, WAL mode, and schema management.

Usage:
    from vinu_infra.sqlite import SQLiteBackend

    class MyBackend(SQLiteBackend):
        SCHEMA = "CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, value TEXT)"
        SCHEMA_VERSION = 1

        def get_items(self):
            conn = self._get_conn()
            return conn.execute("SELECT * FROM items").fetchall()
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class SQLiteBackend:
    SCHEMA: str = ""
    SCHEMA_VERSION: int = 1
    MIGRATIONS: list[tuple[str, str]] = []

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # Every real connection opened by any thread, so close() can close
        # all of them -- threading.local() by itself only lets close() see
        # the calling thread's own connection, silently leaking every other
        # thread's connection (real bug: in a real web server's thread pool,
        # a shutdown-time close() from the main thread closed nothing real).
        # `_generation` lets a thread whose connection was closed by another
        # thread's close() call detect that and transparently reopen, rather
        # than reusing (and raising sqlite3.ProgrammingError on) a stale
        # closed connection object.
        self._all_conns: list[sqlite3.Connection] = []
        self._all_conns_lock = threading.Lock()
        self._generation = 0

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None or getattr(self._local, "gen", -1) != self._generation:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._init_schema(conn)
            self._local.conn = conn
            self._local.gen = self._generation
            with self._all_conns_lock:
                self._all_conns.append(conn)
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        if self.SCHEMA:
            conn.executescript(self.SCHEMA)
        if self.MIGRATIONS:
            from vinu_infra.db import migrate_schema
            migrate_schema(conn, self.SCHEMA_VERSION, self.MIGRATIONS)
        conn.commit()

    def upsert(
        self,
        table: str,
        data: dict[str, Any],
        conflict_columns: list[str],
    ) -> None:
        if not conflict_columns:
            raise ValueError("conflict_columns must not be empty")
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(columns)
        conflict_target = ", ".join(conflict_columns)
        updates = ", ".join(f"{col}=excluded.{col}" for col in columns)
        sql = (
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO UPDATE SET {updates}"
        )
        values = [data[col] for col in columns]
        conn = self._get_conn()
        conn.execute(sql, values)
        conn.commit()

    def insert_or_ignore(
        self,
        table: str,
        data: dict[str, Any],
        conflict_columns: list[str],
    ) -> None:
        if not conflict_columns:
            raise ValueError("conflict_columns must not be empty")
        columns = list(data.keys())
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(columns)
        conflict_target = ", ".join(conflict_columns)
        sql = (
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO NOTHING"
        )
        values = [data[col] for col in columns]
        conn = self._get_conn()
        conn.execute(sql, values)
        conn.commit()

    def upsert_many(
        self,
        table: str,
        records: list[dict[str, Any]],
        conflict_columns: list[str],
    ) -> None:
        """Same real upsert as `upsert()`, but one transaction/commit for
        the whole batch instead of one per row -- real fix for a real
        pattern found in the codebase: a "bulk_add" caller that looped
        calling the single-row `upsert()`, so every row triggered its own
        fsync-backed commit (the classic SQLite anti-pattern), defeating
        the entire point of calling it "bulk". Requires every record to
        share the same real columns (matches every real caller's usage --
        a homogeneous batch, not a mix of different row shapes)."""
        if not conflict_columns:
            raise ValueError("conflict_columns must not be empty")
        if not records:
            return
        columns = list(records[0].keys())
        placeholders = ", ".join("?" for _ in columns)
        col_names = ", ".join(columns)
        conflict_target = ", ".join(conflict_columns)
        updates = ", ".join(f"{col}=excluded.{col}" for col in columns)
        sql = (
            f"INSERT INTO {table} ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict_target}) DO UPDATE SET {updates}"
        )
        rows = [[record[col] for col in columns] for record in records]
        conn = self._get_conn()
        conn.executemany(sql, rows)
        conn.commit()

    def health_info(self) -> dict[str, Any]:
        path = str(self._db_path)
        try:
            conn = self._get_conn()
            count = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            return {"db_path": path, "tables": int(count)}
        except Exception as e:
            return {"db_path": path, "error": str(e)}

    def close(self) -> None:
        """Closes every real connection this instance opened, across every
        thread that opened one -- not just the calling thread's own (see
        `_all_conns` note in __init__). Bumps `_generation` so any other
        thread's next `_get_conn()` call detects its cached connection is
        stale and transparently opens a fresh one, instead of reusing (and
        getting sqlite3.ProgrammingError from) the one just closed here."""
        with self._all_conns_lock:
            conns, self._all_conns = self._all_conns, []
            self._generation += 1
        for conn in conns:
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self._local.conn = None

    def __enter__(self) -> SQLiteBackend:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
