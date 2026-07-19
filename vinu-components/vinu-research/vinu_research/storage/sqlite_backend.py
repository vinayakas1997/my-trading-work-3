from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vinu_research.storage.models import ResearchRunRecord, STATUS_APPROVED, STATUS_DELETED, STATUS_DONE


_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_idea TEXT NOT NULL,
    symbol TEXT NOT NULL,
    from_date TEXT NOT NULL,
    to_date TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    total_iterations INTEGER NOT NULL DEFAULT 0,
    best_iteration INTEGER NOT NULL DEFAULT -1,
    best_sharpe REAL NOT NULL DEFAULT 0.0,
    best_max_dd REAL NOT NULL DEFAULT 0.0,
    report_md TEXT NOT NULL DEFAULT '',
    error_message TEXT,
    approved INTEGER NOT NULL DEFAULT 0,
    approved_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_research_status ON research_runs(status);
CREATE INDEX IF NOT EXISTS idx_research_symbol ON research_runs(symbol);
"""


class ResearchStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self.db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self) -> ResearchStorage:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def insert_run(self, record: ResearchRunRecord) -> ResearchRunRecord:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            """INSERT INTO research_runs
                (user_idea, symbol, from_date, to_date, status, total_iterations,
                 best_iteration, best_sharpe, best_max_dd, report_md, error_message,
                 approved, approved_at, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.user_idea, record.symbol, record.from_date, record.to_date,
                record.status, record.total_iterations, record.best_iteration,
                record.best_sharpe, record.best_max_dd, record.report_md,
                record.error_message, 0, "", now, now,
            ),
        )
        conn.commit()
        record.id = cur.lastrowid
        record.created_at = now
        record.updated_at = now
        return record

    def get_run(self, run_id: int) -> ResearchRunRecord | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM research_runs WHERE id = ?", (run_id,)
        ).fetchone()
        return self._row_to_record(row) if row else None

    def list_runs(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[ResearchRunRecord]:
        conn = self._get_conn()
        conditions = ["status != ?"]
        params: list[Any] = [STATUS_DELETED]
        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if status:
            conditions.append("status = ?")
            params.append(status)
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM research_runs WHERE {' AND '.join(conditions)} ORDER BY created_at DESC, id DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def update_run(self, record: ResearchRunRecord) -> ResearchRunRecord | None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        # Coarse clocks (Windows) can return the same tick as the insert; nudge
        # forward so updated_at always advances past the previous value.
        if record.updated_at and now <= record.updated_at:
            try:
                prev_dt = datetime.fromisoformat(record.updated_at)
                now = (prev_dt + timedelta(microseconds=1)).isoformat()
            except ValueError:
                pass
        conn.execute(
            """UPDATE research_runs SET
                status = ?, total_iterations = ?, best_iteration = ?,
                best_sharpe = ?, best_max_dd = ?, report_md = ?,
                error_message = ?, updated_at = ?
               WHERE id = ?""",
            (
                record.status, record.total_iterations, record.best_iteration,
                record.best_sharpe, record.best_max_dd, record.report_md,
                record.error_message, now, record.id,
            ),
        )
        conn.commit()
        record.updated_at = now
        return record

    def approve_run(self, run_id: int) -> ResearchRunRecord | None:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "UPDATE research_runs SET status = ?, approved = 1, approved_at = ?, updated_at = ? WHERE id = ? AND status = ?",
            (STATUS_APPROVED, now, now, run_id, STATUS_DONE),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        return self.get_run(run_id)

    def delete_run(self, run_id: int) -> bool:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        cur = conn.execute(
            "UPDATE research_runs SET status = ?, updated_at = ? WHERE id = ? AND status != ?",
            (STATUS_DELETED, now, run_id, STATUS_DELETED),
        )
        conn.commit()
        return cur.rowcount > 0

    def health_info(self) -> dict[str, Any]:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM research_runs").fetchone()[0]
        by_status = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM research_runs GROUP BY status"
        ).fetchall()
        return {
            "db_path": str(self.db_path),
            "db_size_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "total_runs": total,
            "status_counts": {r["status"]: r["cnt"] for r in by_status},
        }

    @staticmethod
    def _row_to_record(row: sqlite3.Row | None) -> ResearchRunRecord | None:
        if row is None:
            return None
        return ResearchRunRecord(
            id=row["id"],
            user_idea=row["user_idea"],
            symbol=row["symbol"],
            from_date=row["from_date"],
            to_date=row["to_date"],
            status=row["status"],
            total_iterations=row["total_iterations"],
            best_iteration=row["best_iteration"],
            best_sharpe=row["best_sharpe"],
            best_max_dd=row["best_max_dd"],
            report_md=row["report_md"],
            error_message=row["error_message"],
            approved=bool(row["approved"]),
            approved_at=row["approved_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
