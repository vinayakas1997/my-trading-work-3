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
    updated_at TEXT NOT NULL,
    strategy_code TEXT NOT NULL DEFAULT '',
    source_run_id INTEGER,
    initial_sharpe REAL NOT NULL DEFAULT 0.0,
    initial_max_dd REAL NOT NULL DEFAULT 0.0,
    deflated_sharpe REAL NOT NULL DEFAULT 0.0,
    holdout_passed INTEGER,
    stress_test_passed INTEGER,
    last_validated_ts TEXT NOT NULL DEFAULT '',
    revalidation_count INTEGER NOT NULL DEFAULT 0,
    last_revalidation_verdict INTEGER
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
            self._migrate_schema(conn)
            self._local.conn = conn
        return conn

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        """Add columns to an artifacts table created before they existed."""
        cols = {row[1] for row in conn.execute("PRAGMA table_info(artifacts)")}
        migrations = [
            ("strategy_code", "TEXT NOT NULL DEFAULT ''"),
            ("source_run_id", "INTEGER"),
            ("initial_sharpe", "REAL NOT NULL DEFAULT 0.0"),
            ("initial_max_dd", "REAL NOT NULL DEFAULT 0.0"),
            ("deflated_sharpe", "REAL NOT NULL DEFAULT 0.0"),
            ("holdout_passed", "INTEGER"),
            ("stress_test_passed", "INTEGER"),
            ("last_validated_ts", "TEXT NOT NULL DEFAULT ''"),
            ("revalidation_count", "INTEGER NOT NULL DEFAULT 0"),
            ("last_revalidation_verdict", "INTEGER"),
        ]
        for name, typedef in migrations:
            if name not in cols:
                try:
                    conn.execute(f"ALTER TABLE artifacts ADD COLUMN {name} {typedef}")
                except sqlite3.OperationalError:
                    pass
        conn.commit()

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
                signal_definition, entry_rules, exit_rules, created_at, updated_at,
                strategy_code, source_run_id, initial_sharpe, initial_max_dd, deflated_sharpe,
                holdout_passed, stress_test_passed,
                last_validated_ts, revalidation_count, last_revalidation_verdict)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                artifact.strategy_code,
                artifact.source_run_id,
                artifact.initial_sharpe,
                artifact.initial_max_dd,
                artifact.deflated_sharpe,
                None if artifact.holdout_passed is None else int(artifact.holdout_passed),
                None if artifact.stress_test_passed is None else int(artifact.stress_test_passed),
                artifact.last_validated_ts,
                artifact.revalidation_count,
                None if artifact.last_revalidation_verdict is None else int(artifact.last_revalidation_verdict),
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

    def list_artifacts_for_symbol(
        self,
        symbol: str,
        statuses: list[ArtifactStatus] | None = None,
    ) -> list[Artifact]:
        """Artifacts whose universe includes `symbol`, optionally filtered by status.

        Filters in Python rather than SQL — `universe` is stored as a JSON text
        column and the artifact count per symbol is small, so a JSON1 query
        isn't worth the added dependency risk.
        """
        symbol = symbol.upper()
        wanted = {s.value for s in statuses} if statuses else None
        return [
            a for a in self.list_artifacts()
            if symbol in {u.upper() for u in a.universe}
            and (wanted is None or a.status.value in wanted)
        ]

    def list_artifacts_by_statuses(
        self,
        statuses: list[ArtifactStatus] | None = None,
        type_: str | None = None,
    ) -> list[Artifact]:
        """List artifacts matching any of the given statuses.

        Unlike `list_artifacts` which accepts a single status, this allows
        querying across multiple statuses (e.g. ACTIVE + MONITORING) in one
        query. Returns all artifacts when statuses is None or empty.
        """
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []
        if statuses:
            placeholders = ",".join("?" for _ in statuses)
            conditions.append(f"status IN ({placeholders})")
            params.extend(s.value for s in statuses)
        if type_ is not None:
            conditions.append("type = ?")
            params.append(type_)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM artifacts {where} ORDER BY created_at DESC", params
        ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    def list_stale_artifacts(
        self,
        days: int = 30,
        statuses: list[ArtifactStatus] | None = None,
    ) -> list[Artifact]:
        """Return artifacts whose `last_validated_ts` is older than `days`, or never validated.
        
        Falls back to `created_at` when `last_validated_ts` is empty (an artifact
        that was created before re-validation tracking existed is treated as stale).
        """
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = self._get_conn()
        wanted = [s.value for s in statuses] if statuses else ["ACTIVE", "MONITORING"]
        placeholders = ",".join("?" for _ in wanted)
        rows = conn.execute(
            f"""SELECT * FROM artifacts
                WHERE status IN ({placeholders})
                  AND last_validated_ts < ?
                ORDER BY last_validated_ts ASC""",
            [*wanted, cutoff],
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
            strategy_code=row["strategy_code"] if "strategy_code" in row.keys() else "",
            source_run_id=row["source_run_id"] if "source_run_id" in row.keys() else None,
            initial_sharpe=row["initial_sharpe"] if "initial_sharpe" in row.keys() else 0.0,
            initial_max_dd=row["initial_max_dd"] if "initial_max_dd" in row.keys() else 0.0,
            deflated_sharpe=row["deflated_sharpe"] if "deflated_sharpe" in row.keys() else 0.0,
            holdout_passed=(
                None if "holdout_passed" not in row.keys() or row["holdout_passed"] is None
                else bool(row["holdout_passed"])
            ),
            stress_test_passed=(
                None if "stress_test_passed" not in row.keys() or row["stress_test_passed"] is None
                else bool(row["stress_test_passed"])
            ),
            last_validated_ts=row["last_validated_ts"] if "last_validated_ts" in row.keys() else "",
            revalidation_count=row["revalidation_count"] if "revalidation_count" in row.keys() else 0,
            last_revalidation_verdict=(
                None if "last_revalidation_verdict" not in row.keys() or row["last_revalidation_verdict"] is None
                else bool(row["last_revalidation_verdict"])
            ),
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
