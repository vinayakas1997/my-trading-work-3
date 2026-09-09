from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend


class PaperPerformanceStore(SQLiteBackend):
    """Persistent SQLite store for per-artifact paper-trading daily returns.

    G2 (ats-status-and-next-steps.md:100): was in-memory dict
    ``broker/performance_store.py`` ("non-persistent for v1") -- Shadow needs
    >=5 paper days (min_paper_days) but data reset on every restart, so the
    gate could never actually accumulate. Now SQLite-backed at a shared,
    on-disk path (same pattern as RebalanceRequestQueue
    ``trade_plan/rebalance_intake.py`` and ``trade_plan_book.db``) so a
    restart does not wipe the 5-day window. Thread-safe via
    ``SQLiteBackend`` WAL + busy_timeout, same as every other agent store.
    In-memory ``:memory:`` remains available for isolated tests by passing
    that path explicitly.
    """

    SCHEMA = """
    CREATE TABLE IF NOT EXISTS paper_performance (
        artifact_id TEXT PRIMARY KEY,
        returns_json TEXT NOT NULL,
        updated_at REAL NOT NULL,
        meta_json TEXT NOT NULL DEFAULT '{}'
    );
    """
    SCHEMA_VERSION = 2

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        super().__init__(db_path)
        self._ensure_v2()

    def _ensure_v2(self) -> None:
        # Same 4-field shape as rehearsal (14): run_id + regime + conditions.
        conn = self._get_conn()
        cols = [r[1] for r in conn.execute("PRAGMA table_info(paper_performance)").fetchall()]
        if "meta_json" not in cols:
            conn.execute("ALTER TABLE paper_performance ADD COLUMN meta_json TEXT NOT NULL DEFAULT '{}'")
        conn.commit()

    def record_meta(self, artifact_id: str, meta: dict[str, Any]) -> None:
        self._ensure_v2()
        conn = self._get_conn()
        conn.execute(
            "UPDATE paper_performance SET meta_json = ? WHERE artifact_id = ?",
            (json.dumps(meta), artifact_id),
        )
        if conn.total_changes == 0:
            self.upsert(
                "paper_performance",
                {"artifact_id": artifact_id, "returns_json": "[]", "updated_at": time.time(), "meta_json": json.dumps(meta)},
                conflict_columns=["artifact_id"],
            )
        else:
            conn.commit()

    def get_meta(self, artifact_id: str) -> dict[str, Any]:
        self._ensure_v2()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT meta_json FROM paper_performance WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        if row is None:
            return {}
        try:
            data = json.loads(row["meta_json"])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def record_daily_return(self, artifact_id: str, daily_return: float) -> None:
        existing = self.get_daily_returns(artifact_id)
        existing.append(float(daily_return))
        self.record_daily_returns(artifact_id, existing)

    def record_daily_returns(self, artifact_id: str, returns: list[float]) -> None:
        payload = json.dumps([float(x) for x in (returns or [])])
        self.upsert(
            "paper_performance",
            {"artifact_id": artifact_id, "returns_json": payload, "updated_at": time.time()},
            conflict_columns=["artifact_id"],
        )

    def get_daily_returns(self, artifact_id: str) -> list[float]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT returns_json FROM paper_performance WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        if row is None:
            return []
        try:
            data = json.loads(row["returns_json"])
            return [float(x) for x in data] if isinstance(data, list) else []
        except Exception:
            return []

    def get_all(self) -> dict[str, list[float]]:
        conn = self._get_conn()
        rows = conn.execute("SELECT artifact_id, returns_json FROM paper_performance").fetchall()
        out: dict[str, list[float]] = {}
        for r in rows:
            try:
                vals = json.loads(r["returns_json"])
                out[r["artifact_id"]] = [float(x) for x in vals] if isinstance(vals, list) else []
            except Exception:
                out[r["artifact_id"]] = []
        return dict(out)

    def clear(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM paper_performance")
        conn.commit()


def _persistent_path() -> Path:
    # Docker: VINU_AGENT_DATA_ROOT=/data (bind ./data/agent:/data)
    # Host-direct: fallback to Path.home()/".vinu"
    # Keep the same env contract as AgentConfig.load_config() data_root
    raw = os.environ.get("VINU_AGENT_DATA_ROOT", "").strip()
    if raw:
        return Path(raw) / "paper_performance.db"
    # No env set -- are we inside a container with /data mounted?
    if Path("/data").exists():
        return Path("/data") / "paper_performance.db"
    return Path.home() / ".vinu" / "paper_performance.db"


_store: PaperPerformanceStore | None = None


def get_store() -> PaperPerformanceStore:
    global _store
    if _store is None:
        _store = PaperPerformanceStore(str(_persistent_path()))
    return _store
