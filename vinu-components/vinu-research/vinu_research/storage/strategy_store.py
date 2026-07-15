from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_research.models import Artifact, ArtifactStatus, BenchEntry, DecaySnapshot

_SCHEMA = """
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    name TEXT NOT NULL,
    universe TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'CREATED',
    decay_horizon INTEGER NOT NULL DEFAULT 60,
    signal_definition TEXT NOT NULL DEFAULT '',
    entry_rules TEXT NOT NULL DEFAULT '',
    exit_rules TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bench_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    date TEXT NOT NULL,
    ic REAL NOT NULL DEFAULT 0.0,
    ir REAL NOT NULL DEFAULT 0.0,
    ic_positive INTEGER NOT NULL DEFAULT 0,
    sharpe REAL NOT NULL DEFAULT 0.0,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE TABLE IF NOT EXISTS decay_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL,
    evaluation TEXT NOT NULL,
    ic_ratio REAL NOT NULL DEFAULT 0.0,
    rolling_ir REAL NOT NULL DEFAULT 0.0,
    ic_positive_ratio REAL NOT NULL DEFAULT 0.0,
    rolling_sharpe REAL NOT NULL DEFAULT 0.0,
    n_entries INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_bench_artifact ON bench_history(artifact_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_artifact ON decay_snapshots(artifact_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_status ON artifacts(status);
"""


class SqliteStrategyStore:
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
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            self._local.conn = conn
        return conn

    def close(self) -> None:
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            conn.close()
            self._local.conn = None

    def __enter__(self) -> SqliteStrategyStore:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def upsert_artifact(self, artifact: Artifact) -> Artifact:
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        import json
        conn.execute(
            """INSERT OR REPLACE INTO artifacts
               (artifact_id, type, name, universe, status, decay_horizon,
                signal_definition, entry_rules, exit_rules, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                artifact.artifact_id,
                artifact.type,
                artifact.name,
                json.dumps(artifact.universe),
                artifact.status.value,
                artifact.decay_horizon,
                artifact.signal_definition,
                artifact.entry_rules,
                artifact.exit_rules,
                artifact.created_at or now,
                now,
            ),
        )
        conn.commit()
        artifact.updated_at = now
        return artifact

    def get_artifact(self, artifact_id: str) -> Artifact | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM artifacts WHERE artifact_id = ?", (artifact_id,)
        ).fetchone()
        return self._row_to_artifact(row) if row else None

    def list_artifacts(
        self,
        status: ArtifactStatus | None = None,
        type_: str | None = None,
    ) -> list[Artifact]:
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []
        if status is not None:
            conditions.append("status = ?")
            params.append(status.value)
        if type_ is not None:
            conditions.append("type = ?")
            params.append(type_)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM artifacts {where} ORDER BY created_at DESC", params
        ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def delete_artifact(self, artifact_id: str) -> bool:
        conn = self._get_conn()
        conn.execute("DELETE FROM decay_snapshots WHERE artifact_id = ?", (artifact_id,))
        conn.execute("DELETE FROM bench_history WHERE artifact_id = ?", (artifact_id,))
        cur = conn.execute("DELETE FROM artifacts WHERE artifact_id = ?", (artifact_id,))
        conn.commit()
        return cur.rowcount > 0

    def append_bench_entry(self, entry: BenchEntry) -> BenchEntry:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO bench_history
               (artifact_id, date, ic, ir, ic_positive, sharpe)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (entry.artifact_id, entry.date, entry.ic, entry.ir,
             int(entry.ic_positive), entry.sharpe),
        )
        conn.commit()
        return entry

    def get_bench_history(self, artifact_id: str) -> list[BenchEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM bench_history WHERE artifact_id = ? ORDER BY date ASC",
            (artifact_id,),
        ).fetchall()
        return [self._row_to_bench_entry(r) for r in rows]

    def save_snapshot(self, snapshot: DecaySnapshot) -> DecaySnapshot:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO decay_snapshots
               (artifact_id, evaluation, ic_ratio, rolling_ir,
                ic_positive_ratio, rolling_sharpe, n_entries, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.artifact_id,
                snapshot.evaluation,
                snapshot.ic_ratio,
                snapshot.rolling_ir,
                snapshot.ic_positive_ratio,
                snapshot.rolling_sharpe,
                snapshot.n_entries,
                snapshot.timestamp,
            ),
        )
        conn.commit()
        return snapshot

    def get_latest_snapshot(self, artifact_id: str) -> DecaySnapshot | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM decay_snapshots WHERE artifact_id = ? ORDER BY id DESC LIMIT 1",
            (artifact_id,),
        ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def get_snapshots(self, artifact_id: str) -> list[DecaySnapshot]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM decay_snapshots WHERE artifact_id = ? ORDER BY id DESC",
            (artifact_id,),
        ).fetchall()
        return [self._row_to_snapshot(r) for r in rows]

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> Artifact:
        import json
        return Artifact(
            artifact_id=row["artifact_id"],
            type=row["type"],
            name=row["name"],
            universe=json.loads(row["universe"]),
            status=ArtifactStatus(row["status"]),
            decay_horizon=row["decay_horizon"],
            signal_definition=row["signal_definition"],
            entry_rules=row["entry_rules"],
            exit_rules=row["exit_rules"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _row_to_bench_entry(row: sqlite3.Row) -> BenchEntry:
        return BenchEntry(
            artifact_id=row["artifact_id"],
            date=row["date"],
            ic=row["ic"],
            ir=row["ir"],
            ic_positive=bool(row["ic_positive"]),
            sharpe=row["sharpe"],
        )

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row) -> DecaySnapshot:
        return DecaySnapshot(
            artifact_id=row["artifact_id"],
            evaluation=row["evaluation"],
            ic_ratio=row["ic_ratio"],
            rolling_ir=row["rolling_ir"],
            ic_positive_ratio=row["ic_positive_ratio"],
            rolling_sharpe=row["rolling_sharpe"],
            n_entries=row["n_entries"],
            timestamp=row["timestamp"],
        )
