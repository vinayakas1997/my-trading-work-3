from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    angle_name  TEXT NOT NULL,
    run_id      TEXT NOT NULL UNIQUE,
    started_at  TEXT NOT NULL,
    analysis_from TEXT,
    analysis_until TEXT,
    stored_at   TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'completed',
    error       TEXT,
    row_count   INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_runs_symbol ON runs(symbol);
CREATE INDEX IF NOT EXISTS idx_runs_angle ON runs(angle_name);
"""


class RunLog:
    """SQLite run log — tracks every analysis run by symbol + angle."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA_SQL)

    def record_run(
        self,
        symbol: str,
        angle_name: str,
        run_id: str,
        *,
        analysis_from: int | None = None,
        analysis_until: int | None = None,
        status: str = "completed",
        error: str | None = None,
        row_count: int = 0,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """INSERT OR REPLACE INTO runs
               (symbol, angle_name, run_id, started_at, analysis_from, analysis_until, stored_at, status, error, row_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                symbol,
                angle_name,
                run_id,
                now,
                datetime.fromtimestamp(analysis_from, tz=timezone.utc).isoformat() if analysis_from else None,
                datetime.fromtimestamp(analysis_until, tz=timezone.utc).isoformat() if analysis_until else None,
                now,
                status,
                error,
                row_count,
            ),
        )
        self._conn.commit()

    def get_runs(
        self,
        symbol: str | None = None,
        angle_name: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        query = "SELECT * FROM runs WHERE 1=1"
        params: list[Any] = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if angle_name:
            query += " AND angle_name = ?"
            params.append(angle_name)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_latest_run(self, symbol: str, angle_name: str) -> dict[str, Any] | None:
        cursor = self._conn.execute(
            "SELECT * FROM runs WHERE symbol = ? AND angle_name = ? ORDER BY started_at DESC LIMIT 1",
            (symbol, angle_name),
        )
        rows = cursor.fetchall()
        if not rows:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, rows[0]))

    def close(self) -> None:
        self._conn.close()
