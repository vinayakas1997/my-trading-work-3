from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any


class MetaStorage:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._local = threading.local()
        self._connections: set[sqlite3.Connection] = set()
        self._close_lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._ensure_config_hash_column()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            with self._close_lock:
                self._connections.add(conn)
        return self._local.conn

    def _init_schema(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS simulation_runs (
                run_id TEXT PRIMARY KEY,
                strategy_name TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                config TEXT NOT NULL,
                metrics TEXT NOT NULL,
                benchmark_metrics TEXT,
                equity_points INTEGER DEFAULT 0,
                trade_count INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_runs_strategy ON simulation_runs(strategy_name);
            CREATE INDEX IF NOT EXISTS idx_runs_timestamp ON simulation_runs(timestamp);
        """)

    def _ensure_config_hash_column(self) -> None:
        conn = self._get_conn()
        cursor = conn.execute("PRAGMA table_info(simulation_runs)")
        columns = [row[1] for row in cursor.fetchall()]
        if "config_hash" not in columns:
            conn.execute("ALTER TABLE simulation_runs ADD COLUMN config_hash TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_config_hash ON simulation_runs(config_hash)")

    def insert_run(
        self,
        run_id: str,
        strategy_name: str,
        timestamp: datetime,
        config: dict[str, Any],
        metrics: dict[str, float],
        *,
        config_hash: str = "",
        benchmark_metrics: dict[str, dict[str, float]] | None = None,
        equity_points: int = 0,
        trade_count: int = 0,
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO simulation_runs
               (run_id, strategy_name, timestamp, config, metrics, benchmark_metrics, equity_points, trade_count, config_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                run_id,
                strategy_name,
                timestamp.isoformat(),
                json.dumps(config, default=str),
                json.dumps(metrics, default=str),
                json.dumps(benchmark_metrics or {}, default=str),
                equity_points,
                trade_count,
                config_hash,
            ),
        )
        conn.commit()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM simulation_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        r = dict(row)
        r["config"] = json.loads(r["config"])
        r["metrics"] = json.loads(r["metrics"])
        r["benchmark_metrics"] = json.loads(r["benchmark_metrics"])
        return r

    def get_run_by_config_hash(self, config_hash: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM simulation_runs WHERE config_hash = ? ORDER BY timestamp DESC LIMIT 1",
            (config_hash,),
        ).fetchone()
        if row is None:
            return None
        r = dict(row)
        r["config"] = json.loads(r["config"])
        r["metrics"] = json.loads(r["metrics"])
        r["benchmark_metrics"] = json.loads(r["benchmark_metrics"])
        return r

    def list_runs(self, strategy_name: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if strategy_name:
            rows = conn.execute(
                "SELECT * FROM simulation_runs WHERE strategy_name = ? ORDER BY timestamp DESC",
                (strategy_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM simulation_runs ORDER BY timestamp DESC"
            ).fetchall()
        result = []
        for row in rows:
            r = dict(row)
            r["config"] = json.loads(r["config"])
            r["metrics"] = json.loads(r["metrics"])
            r["benchmark_metrics"] = json.loads(r["benchmark_metrics"])
            result.append(r)
        return result

    def delete_run(self, run_id: str) -> bool:
        conn = self._get_conn()
        cur = conn.execute(
            "DELETE FROM simulation_runs WHERE run_id = ?", (run_id,)
        )
        conn.commit()
        return cur.rowcount > 0

    def delete_runs(self, strategy_name: str | None = None) -> int:
        conn = self._get_conn()
        if strategy_name:
            cur = conn.execute(
                "DELETE FROM simulation_runs WHERE strategy_name = ?", (strategy_name,)
            )
        else:
            cur = conn.execute("DELETE FROM simulation_runs")
        conn.commit()
        return cur.rowcount

    def close(self) -> None:
        with self._close_lock:
            for conn in self._connections:
                conn.close()
            self._connections.clear()
        if hasattr(self._local, "conn") and self._local.conn is not None:
            self._local.conn = None
