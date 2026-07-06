from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

LOG = logging.getLogger(__name__)


class MetaStorage:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
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
        """)
        self._conn.commit()

    def register_strategy(self, name: str, description: str = "", schedule: str = "daily") -> None:
        self._conn.execute(
            """INSERT OR REPLACE INTO strategy_registry (name, description, schedule, updated_at)
               VALUES (?, ?, ?, datetime('now'))""",
            (name, description, schedule),
        )
        self._conn.commit()

    def get_registered_strategies(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT name, description, schedule, enabled FROM strategy_registry ORDER BY name"
        ).fetchall()
        return [
            {"name": r[0], "description": r[1], "schedule": r[2], "enabled": bool(r[3])}
            for r in rows
        ]

    def log_run(self, strategy_name: str, run_id: str, symbol: str | None = None, status: str = "completed", metadata: dict[str, Any] | None = None) -> None:
        self._conn.execute(
            """INSERT INTO strategy_runs (strategy_name, run_id, symbol, timestamp, status, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (strategy_name, run_id, symbol, datetime.utcnow().isoformat(), status, str(metadata or {})),
        )
        self._conn.commit()

    def get_runs(self, strategy_name: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        if strategy_name:
            rows = self._conn.execute(
                "SELECT strategy_name, run_id, symbol, timestamp, status FROM strategy_runs WHERE strategy_name=? ORDER BY id DESC LIMIT ?",
                (strategy_name, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT strategy_name, run_id, symbol, timestamp, status FROM strategy_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {"strategy_name": r[0], "run_id": r[1], "symbol": r[2], "timestamp": r[3], "status": r[4]}
            for r in rows
        ]

    def delete_runs(self, strategy_name: str | None = None) -> int:
        if strategy_name:
            cursor = self._conn.execute("DELETE FROM strategy_runs WHERE strategy_name=?", (strategy_name,))
        else:
            cursor = self._conn.execute("DELETE FROM strategy_runs")
        self._conn.commit()
        return cursor.rowcount

    def delete_run_by_id(self, run_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM strategy_runs WHERE run_id=?", (run_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_strategy(self, name: str) -> bool:
        self._conn.execute("DELETE FROM strategy_runs WHERE strategy_name=?", (name,))
        cursor = self._conn.execute("DELETE FROM strategy_registry WHERE name=?", (name,))
        self._conn.commit()
        return cursor.rowcount > 0

    def close(self) -> None:
        self._conn.close()
