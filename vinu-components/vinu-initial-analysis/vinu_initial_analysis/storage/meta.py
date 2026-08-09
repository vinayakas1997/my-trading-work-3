from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend


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
    row_count   INTEGER DEFAULT 0,
    granularity TEXT NOT NULL DEFAULT '1D',
    tier        TEXT NOT NULL DEFAULT 'tier2',
    duration_seconds REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_symbol ON runs(symbol);
CREATE INDEX IF NOT EXISTS idx_runs_angle ON runs(angle_name);
"""
# NOTE: this is a clean-slate schema addition, not a live migration -- this
# redesign phase confirmed no vinu_initial_analysis_runs.db with real rows
# exists anywhere in the working tree, so a plain column addition (rather
# than migration scaffolding) is correct here. See 03-storage-design.md
# section 7 for the `runs(... granularity, tier ...)` table this mirrors.


class RunLog(SQLiteBackend):
    """SQLite run log — tracks every analysis run by symbol + angle.

    This is the single source of truth for "which run is current" — see
    `AngleStorage._resolve_latest_path()`, which reads through here instead
    of scanning the parquet directory by file mtime.
    """

    SCHEMA = SCHEMA_SQL

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
        granularity: str = "1D",
        tier: str = "tier2",
        duration_seconds: float | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO runs
               (symbol, angle_name, run_id, started_at, analysis_from, analysis_until, stored_at, status, error, row_count, granularity, tier, duration_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                granularity,
                tier,
                duration_seconds,
            ),
        )
        conn.commit()

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

        conn = self._get_conn()
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def get_latest_run(
        self,
        symbol: str,
        angle_name: str,
        *,
        completed_only: bool = True,
        granularity: str = "1D",
        tier: str = "tier2",
    ) -> dict[str, Any] | None:
        """Resolve the current run for symbol+angle+granularity+tier — the SQL
        equivalent of
        `ORDER BY computed_at DESC LIMIT 1 WHERE status='ok' AND granularity=? AND tier=?`
        from 03-storage-design.md section 7. This is what AngleStorage reads
        through instead of picking the newest file by mtime.

        granularity/tier are filtered exactly (not wildcarded): a 1H run and a
        1D run of the same angle are different results, and a tier3 run must
        never masquerade as the tier2 "latest" (or vice versa).
        """
        query = "SELECT * FROM runs WHERE symbol = ? AND angle_name = ? AND granularity = ? AND tier = ?"
        params: list[Any] = [symbol, angle_name, granularity, tier]
        if completed_only:
            query += " AND status = 'completed'"
        query += " ORDER BY started_at DESC LIMIT 1"
        conn = self._get_conn()
        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        if not rows:
            return None
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, rows[0]))

    def has_existing_run(
        self,
        symbol: str,
        angle_name: str,
        analysis_from: int | None = None,
        analysis_until: int | None = None,
        *,
        granularity: str = "1D",
        tier: str = "tier2",
    ) -> bool:
        """Check if a completed run exists for the given params.

        Scoped by granularity/tier too: a 1H run and a 1D run over the same
        symbol/angle/window are NOT the same run, so they must not
        short-circuit each other's "already computed" check.
        """
        query = (
            "SELECT 1 FROM runs WHERE symbol = ? AND angle_name = ? "
            "AND status = 'completed' AND granularity = ? AND tier = ?"
        )
        params: list[Any] = [symbol, angle_name, granularity, tier]
        if analysis_from is not None:
            query += " AND analysis_from = ?"
            params.append(datetime.fromtimestamp(analysis_from, tz=timezone.utc).isoformat())
        if analysis_until is not None:
            query += " AND analysis_until = ?"
            params.append(datetime.fromtimestamp(analysis_until, tz=timezone.utc).isoformat())
        query += " LIMIT 1"
        conn = self._get_conn()
        cursor = conn.execute(query, params)
        return cursor.fetchone() is not None

    def delete_by_angle(self, angle_name: str) -> int:
        """Deletes every run row for this angle. Returns the number deleted.

        Used by `storage/admin.py`'s `delete_angle()` to keep this table in
        sync when an angle's files are removed from disk — without this,
        `get_latest_run()` would keep resolving to a run_id whose parquet
        file no longer exists.
        """
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM runs WHERE angle_name = ?", (angle_name,))
        conn.commit()
        return cursor.rowcount
