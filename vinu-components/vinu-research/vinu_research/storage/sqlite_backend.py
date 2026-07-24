from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from vinu_lib.sqlite import SQLiteBackend
from vinu_research.storage.models import ResearchRunRecord, STATUS_APPROVED, STATUS_DELETED, STATUS_DONE

SCHEMA_VERSION = 2

_SCHEMA = f"""
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
    updated_at TEXT NOT NULL,
    strategy_code TEXT NOT NULL DEFAULT '',
    deflated_sharpe REAL NOT NULL DEFAULT 0.0,
    holdout_passed INTEGER,
    stress_test_passed INTEGER
);
CREATE INDEX IF NOT EXISTS idx_research_status ON research_runs(status);
CREATE INDEX IF NOT EXISTS idx_research_symbol ON research_runs(symbol);
CREATE TABLE IF NOT EXISTS research_catalog (
    symbol TEXT PRIMARY KEY,
    lifetime_trial_count INTEGER NOT NULL DEFAULT 0,
    last_run_id INTEGER,
    last_run_ts TEXT,
    last_validated_ts TEXT,
    best_sharpe_ever REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE IF NOT EXISTS iteration_checkpoints (
    run_id INTEGER NOT NULL,
    iteration INTEGER NOT NULL,
    code TEXT NOT NULL DEFAULT '',
    metrics TEXT,
    critic_verdict TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (run_id, iteration)
);
"""

_MIGRATIONS: list[tuple[str, str]] = [
    ("ALTER TABLE research_runs ADD COLUMN strategy_code TEXT NOT NULL DEFAULT ''", "add_strategy_code"),
    ("ALTER TABLE research_runs ADD COLUMN deflated_sharpe REAL NOT NULL DEFAULT 0.0", "add_deflated_sharpe"),
    ("ALTER TABLE research_runs ADD COLUMN holdout_passed INTEGER", "add_holdout_passed"),
    ("ALTER TABLE research_runs ADD COLUMN stress_test_passed INTEGER", "add_stress_test_passed"),
]


class ResearchStorage(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = _MIGRATIONS

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.db_path = self._db_path

    def close(self) -> None:
        conn: sqlite3.Connection | None = getattr(self._local, "conn", None)
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
                 approved, approved_at, created_at, updated_at, strategy_code, deflated_sharpe,
                 holdout_passed, stress_test_passed)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.user_idea, record.symbol, record.from_date, record.to_date,
                record.status, record.total_iterations, record.best_iteration,
                record.best_sharpe, record.best_max_dd, record.report_md,
                record.error_message, 0, "", now, now, record.strategy_code,
                record.deflated_sharpe,
                None if record.holdout_passed is None else int(record.holdout_passed),
                None if record.stress_test_passed is None else int(record.stress_test_passed),
            ),
        )
        conn.commit()
        record.id = cur.lastrowid
        record.created_at = now
        record.updated_at = now
        return record

    def get_past_run_summaries(self, symbol: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.list_runs(symbol=symbol, limit=limit)
        return [
            {
                "run_id": r.id,
                "user_idea": r.user_idea,
                "best_sharpe": r.best_sharpe,
                "total_iterations": r.total_iterations,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    def cumulative_trial_count(self, symbol: str) -> int:
        """Sum of `total_iterations` across every past run for this symbol.

        Each iteration inside a research loop backtests one candidate against
        the same historical window, so this is the true number of "shots on
        goal" taken against that symbol's data — not just the count from the
        current run — for deflated-Sharpe multiple-comparisons correction.
        Excludes deleted runs; the run currently in progress isn't in the
        table yet, so callers add its own iteration count on top of this.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(total_iterations), 0) FROM research_runs "
            "WHERE symbol = ? AND status != ?",
            (symbol.upper(), STATUS_DELETED),
        ).fetchone()
        return int(row[0]) if row else 0

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
                error_message = ?, updated_at = ?, strategy_code = ?, deflated_sharpe = ?,
                holdout_passed = ?, stress_test_passed = ?
               WHERE id = ?""",
            (
                record.status, record.total_iterations, record.best_iteration,
                record.best_sharpe, record.best_max_dd, record.report_md,
                record.error_message, now, record.strategy_code,
                record.deflated_sharpe,
                None if record.holdout_passed is None else int(record.holdout_passed),
                None if record.stress_test_passed is None else int(record.stress_test_passed),
                record.id,
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

    # ── Catalog methods ──────────────────────────────────────────────

    def update_catalog_after_run(
        self,
        symbol: str,
        run_id: int,
        trial_count: int,
        sharpe: float,
        validated: bool = False,
    ) -> None:
        """Record a completed research run against a symbol's lifetime catalog.

        `trial_count` must already be the symbol's *full* lifetime trial
        total (prior runs' iterations, via `cumulative_trial_count`, plus this
        run's own) — callers compute that before calling this, so this is a
        plain overwrite of `lifetime_trial_count`, not an additive delta
        (adding here on top of an already-cumulative value would double-count
        prior runs). `best_sharpe_ever` is the one field that genuinely needs
        max-across-history semantics, since callers only ever pass *this*
        run's best Sharpe, not a running best.
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """INSERT INTO research_catalog
               (symbol, lifetime_trial_count, last_run_id, last_run_ts,
                last_validated_ts, best_sharpe_ever, status)
               VALUES (?, ?, ?, ?, ?, ?, 'active')
               ON CONFLICT (symbol) DO UPDATE SET
               lifetime_trial_count = excluded.lifetime_trial_count,
               last_run_id = excluded.last_run_id,
               last_run_ts = excluded.last_run_ts,
               last_validated_ts = COALESCE(excluded.last_validated_ts, last_validated_ts),
               best_sharpe_ever = MAX(best_sharpe_ever, excluded.best_sharpe_ever),
               status = excluded.status""",
            (
                symbol.upper(), trial_count, run_id, now,
                now if validated else None, sharpe,
            ),
        )
        conn.commit()

    def get_catalog_entry(self, symbol: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM research_catalog WHERE symbol = ?", (symbol.upper(),)
        ).fetchone()
        if row is None:
            return None
        return dict(row)

    def list_catalog(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM research_catalog ORDER BY symbol"
        ).fetchall()
        return [dict(r) for r in rows]

    def list_stale_catalog(self, days: int = 30) -> list[dict[str, Any]]:
        conn = self._get_conn()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = conn.execute(
            "SELECT * FROM research_catalog WHERE "
            "last_validated_ts IS NULL OR "
            "last_validated_ts < ? ORDER BY symbol",
            (cutoff.isoformat(),),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Checkpoint methods ───────────────────────────────────────────

    def save_checkpoint(
        self,
        run_id: int,
        iteration: int,
        code: str = "",
        metrics: dict[str, Any] | None = None,
        critic_verdict: str = "",
    ) -> None:
        self.insert_or_ignore(
            "iteration_checkpoints",
            {
                "run_id": run_id,
                "iteration": iteration,
                "code": code,
                "metrics": __import__("json").dumps(metrics or {}),
                "critic_verdict": critic_verdict,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            conflict_columns=["run_id", "iteration"],
        )

    def get_last_checkpoint(self, run_id: int) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM iteration_checkpoints WHERE run_id = ? "
            "ORDER BY iteration DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result["metrics"] = __import__("json").loads(result["metrics"])
        except (ValueError, TypeError):
            result["metrics"] = {}
        return result

    def list_checkpoints(self, run_id: int) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM iteration_checkpoints WHERE run_id = ? "
            "ORDER BY iteration ASC",
            (run_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["metrics"] = __import__("json").loads(d["metrics"])
            except (ValueError, TypeError):
                d["metrics"] = {}
            result.append(d)
        return result

    def delete_checkpoints(self, run_id: int) -> None:
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM iteration_checkpoints WHERE run_id = ?", (run_id,)
        )
        conn.commit()

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
            strategy_code=row["strategy_code"] if "strategy_code" in row.keys() else "",
            deflated_sharpe=row["deflated_sharpe"] if "deflated_sharpe" in row.keys() else 0.0,
            holdout_passed=(
                None if "holdout_passed" not in row.keys() or row["holdout_passed"] is None
                else bool(row["holdout_passed"])
            ),
            stress_test_passed=(
                None if "stress_test_passed" not in row.keys() or row["stress_test_passed"] is None
                else bool(row["stress_test_passed"])
            ),
        )
