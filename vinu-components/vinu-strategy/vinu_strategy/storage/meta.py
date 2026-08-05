from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from vinu_infra.db import migrate_schema

LOG = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name TEXT NOT NULL,
    run_id      TEXT NOT NULL UNIQUE,
    symbol      TEXT,
    timestamp   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    metadata    TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS strategy_registry (
    name        TEXT PRIMARY KEY,
    description TEXT,
    schedule    TEXT DEFAULT 'daily',
    enabled     INTEGER DEFAULT 1,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


class MetaStorage:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            self._migrate(conn)
            self._local.conn = conn
        return conn

    def _migrate(self, conn: sqlite3.Connection) -> None:
        migrate_schema(conn, version=1, migrations=[])

    def register_strategy(self, name: str, description: str = "", schedule: str = "daily") -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO strategy_registry (name, description, schedule, updated_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (name, description, schedule),
        )
        conn.commit()

    def get_registered_strategies(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name, description, schedule, enabled FROM strategy_registry ORDER BY name"
        ).fetchall()
        return [
            {"name": r[0], "description": r[1], "schedule": r[2], "enabled": bool(r[3])}
            for r in rows
        ]

    def log_run(self, strategy_name: str, run_id: str, symbol: str | None = None, status: str = "completed", metadata: dict[str, Any] | None = None) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO strategy_runs (strategy_name, run_id, symbol, timestamp, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (strategy_name, run_id, symbol, datetime.utcnow().isoformat(), status, str(metadata or {})),
        )
        conn.commit()

    def get_runs(self, strategy_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if strategy_name:
            rows = conn.execute(
                "SELECT strategy_name, run_id, symbol, timestamp, status FROM strategy_runs WHERE strategy_name=? ORDER BY id DESC LIMIT ?",
                (strategy_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT strategy_name, run_id, symbol, timestamp, status FROM strategy_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"strategy_name": r[0], "run_id": r[1], "symbol": r[2], "timestamp": r[3], "status": r[4]}
            for r in rows
        ]

    def delete_runs(self, strategy_name: str | None = None) -> int:
        conn = self._get_conn()
        if strategy_name:
            cursor = conn.execute("DELETE FROM strategy_runs WHERE strategy_name=?", (strategy_name,))
        else:
            cursor = conn.execute("DELETE FROM strategy_runs")
        conn.commit()
        return cursor.rowcount

    def delete_run_by_id(self, run_id: str) -> bool:
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM strategy_runs WHERE run_id=?", (run_id,))
        conn.commit()
        return cursor.rowcount > 0

    def delete_strategy(self, name: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM strategy_runs WHERE strategy_name=?", (name,))
        cursor = conn.execute("DELETE FROM strategy_registry WHERE name=?", (name,))
        conn.commit()
        return cursor.rowcount > 0

    def health_info(self) -> dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM strategy_runs").fetchone()[0]
        return {
            "db_path": str(self._db_path),
            "total_runs": total,
        }

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
