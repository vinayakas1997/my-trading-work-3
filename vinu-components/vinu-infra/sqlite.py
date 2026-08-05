"""Shared SQLite backend with thread-local connections, WAL mode, and schema management.

Usage:
    from vinu_lib.sqlite import SQLiteBackend

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

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            self._init_schema(conn)
            self._local.conn = conn
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        if self.SCHEMA:
            conn.executescript(self.SCHEMA)
        if self.MIGRATIONS:
            from vinu_lib.db import migrate_schema
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
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self) -> SQLiteBackend:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
