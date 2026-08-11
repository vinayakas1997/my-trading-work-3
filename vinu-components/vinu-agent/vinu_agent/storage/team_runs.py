"""team_runs / team_tasks tracking: who's running, who's waiting, and each
team run's final verdict. Mirrors the established pattern already used
across this codebase (vinu-tools' feature_requests table, vinu-research's
ResearchRunRecord, swarm's SwarmRun/SwarmTask) rather than inventing a new
shape. See New-talk-agents/01-orchestrator-and-teams-architecture.md.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS team_runs (
    run_id                  TEXT PRIMARY KEY,
    team_name                TEXT NOT NULL,
    triggered_by_session_id  TEXT NOT NULL DEFAULT '',
    status                   TEXT NOT NULL DEFAULT 'pending',
    verdict                  TEXT NOT NULL DEFAULT '',
    result_json              TEXT NOT NULL DEFAULT '{}',
    llm_calls_used            INTEGER NOT NULL DEFAULT 0,
    time_used_seconds         REAL NOT NULL DEFAULT 0.0,
    error_message             TEXT NOT NULL DEFAULT '',
    created_at                TEXT NOT NULL,
    updated_at                TEXT NOT NULL,
    completed_at              TEXT NOT NULL DEFAULT '',
    related_artifact_id       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_team_runs_status ON team_runs(status);
CREATE INDEX IF NOT EXISTS idx_team_runs_session ON team_runs(triggered_by_session_id);

CREATE TABLE IF NOT EXISTS team_tasks (
    task_id      TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    agent_name   TEXT NOT NULL,
    role         TEXT NOT NULL DEFAULT '',
    depends_on   TEXT NOT NULL DEFAULT '[]',
    status       TEXT NOT NULL DEFAULT 'pending',
    result       TEXT NOT NULL DEFAULT '',
    error        TEXT NOT NULL DEFAULT '',
    started_at   TEXT NOT NULL DEFAULT '',
    completed_at TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_team_tasks_run ON team_tasks(run_id);
CREATE INDEX IF NOT EXISTS idx_team_tasks_status ON team_tasks(status);
"""

SCHEMA_VERSION = 2
MIGRATIONS: list[tuple[str, str]] = [
    # ADD COLUMN is a no-op (idempotent "duplicate column name" error, caught
    # by vinu_infra.db.migrate_schema) on a fresh DB, where CREATE TABLE
    # above already included the column -- real work only happens on a
    # pre-existing team_runs.db from before this column existed. The index
    # runs from MIGRATIONS, not the CREATE TABLE block above, specifically
    # so it always runs *after* the ALTER TABLE, never before it on a
    # legacy DB (SCHEMA executescript runs before MIGRATIONS on every
    # connection -- putting the index there would fail referencing a
    # column that doesn't exist yet on an old database).
    (
        "ALTER TABLE team_runs ADD COLUMN related_artifact_id TEXT NOT NULL DEFAULT ''",
        "1.1.0 -- traceability link to the vinu-research Artifact a run produced, see New-talk-agents/implementation/14-*.md",
    ),
    (
        "CREATE INDEX IF NOT EXISTS idx_team_runs_artifact ON team_runs(related_artifact_id)",
        "1.1.0",
    ),
]

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TASK_STATUS_PENDING = "pending"
TASK_STATUS_RUNNING = "running"
TASK_STATUS_COMPLETED = "completed"
TASK_STATUS_FAILED = "failed"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class TeamRun:
    run_id: str
    team_name: str
    triggered_by_session_id: str = ""
    status: str = STATUS_PENDING
    verdict: str = ""
    result_json: dict[str, Any] = field(default_factory=dict)
    llm_calls_used: int = 0
    time_used_seconds: float = 0.0
    error_message: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""
    related_artifact_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["result_json"] = json.dumps(self.result_json)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TeamRun":
        result_json = row.get("result_json", "{}")
        if isinstance(result_json, str):
            try:
                result_json = json.loads(result_json)
            except json.JSONDecodeError:
                result_json = {}
        return cls(
            run_id=row["run_id"],
            team_name=row["team_name"],
            triggered_by_session_id=row.get("triggered_by_session_id", ""),
            status=row.get("status", STATUS_PENDING),
            verdict=row.get("verdict", ""),
            result_json=result_json,
            llm_calls_used=int(row.get("llm_calls_used") or 0),
            time_used_seconds=float(row.get("time_used_seconds") or 0.0),
            error_message=row.get("error_message", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            completed_at=row.get("completed_at", ""),
            related_artifact_id=row.get("related_artifact_id", ""),
        )


@dataclass
class TeamTask:
    task_id: str
    run_id: str
    agent_name: str
    role: str = ""
    depends_on: list[str] = field(default_factory=list)
    status: str = TASK_STATUS_PENDING
    result: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["depends_on"] = json.dumps(self.depends_on)
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TeamTask":
        depends_on = row.get("depends_on", "[]")
        if isinstance(depends_on, str):
            try:
                depends_on = json.loads(depends_on)
            except json.JSONDecodeError:
                depends_on = []
        return cls(
            task_id=row["task_id"],
            run_id=row["run_id"],
            agent_name=row["agent_name"],
            role=row.get("role", ""),
            depends_on=depends_on,
            status=row.get("status", TASK_STATUS_PENDING),
            result=row.get("result", ""),
            error=row.get("error", ""),
            started_at=row.get("started_at", ""),
            completed_at=row.get("completed_at", ""),
        )


class TeamRunStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def create_run(
        self, team_name: str, *, triggered_by_session_id: str = "", related_artifact_id: str = "",
    ) -> TeamRun:
        now = _now()
        run = TeamRun(
            run_id=_new_id(),
            team_name=team_name,
            triggered_by_session_id=triggered_by_session_id,
            related_artifact_id=related_artifact_id,
            created_at=now,
            updated_at=now,
        )
        self.upsert("team_runs", run.to_dict(), conflict_columns=["run_id"])
        return run

    def set_related_artifact_id(self, run_id: str, artifact_id: str) -> None:
        """For the common case where the artifact doesn't exist yet when
        the run starts (e.g. research's own run creates the artifact only
        once its manager reaches PASS) -- set it after the fact rather
        than only at create_run time."""
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_runs SET related_artifact_id = ?, updated_at = ? WHERE run_id = ?",
            (artifact_id, _now(), run_id),
        )
        conn.commit()

    def list_by_artifact_id(self, artifact_id: str) -> list[TeamRun]:
        """Pillar 7's traceability query, made real: every run that ever
        touched a given vinu-research Artifact, in one query."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM team_runs WHERE related_artifact_id = ? ORDER BY created_at ASC",
            (artifact_id,),
        ).fetchall()
        return [TeamRun.from_row(dict(r)) for r in rows]

    def get_run(self, run_id: str) -> Optional[TeamRun]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM team_runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return TeamRun.from_row(dict(row))

    def list_runs(self, *, status: Optional[str] = None, limit: int = 100) -> list[TeamRun]:
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM team_runs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM team_runs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [TeamRun.from_row(dict(r)) for r in rows]

    def mark_running(self, run_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_runs SET status = ?, updated_at = ? WHERE run_id = ?",
            (STATUS_RUNNING, _now(), run_id),
        )
        conn.commit()

    def mark_done(
        self,
        run_id: str,
        *,
        verdict: str,
        result_json: dict[str, Any],
        llm_calls_used: int = 0,
        time_used_seconds: float = 0.0,
    ) -> None:
        now = _now()
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE team_runs
            SET status = ?, verdict = ?, result_json = ?, llm_calls_used = ?,
                time_used_seconds = ?, updated_at = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (STATUS_DONE, verdict, json.dumps(result_json), llm_calls_used,
             time_used_seconds, now, now, run_id),
        )
        conn.commit()

    def mark_failed(self, run_id: str, *, error_message: str) -> None:
        now = _now()
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE team_runs
            SET status = ?, error_message = ?, updated_at = ?, completed_at = ?
            WHERE run_id = ?
            """,
            (STATUS_FAILED, error_message, now, now, run_id),
        )
        conn.commit()

    def mark_cancelled(self, run_id: str) -> None:
        now = _now()
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_runs SET status = ?, updated_at = ?, completed_at = ? WHERE run_id = ?",
            (STATUS_CANCELLED, now, now, run_id),
        )
        conn.commit()

    def add_task(
        self,
        run_id: str,
        *,
        agent_name: str,
        role: str = "",
        depends_on: Optional[list[str]] = None,
    ) -> TeamTask:
        task = TeamTask(
            task_id=_new_id(),
            run_id=run_id,
            agent_name=agent_name,
            role=role,
            depends_on=depends_on or [],
        )
        self.upsert("team_tasks", task.to_dict(), conflict_columns=["task_id"])
        return task

    def list_tasks(self, run_id: str) -> list[TeamTask]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM team_tasks WHERE run_id = ? ORDER BY started_at ASC", (run_id,)
        ).fetchall()
        return [TeamTask.from_row(dict(r)) for r in rows]

    def mark_task_running(self, task_id: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_tasks SET status = ?, started_at = ? WHERE task_id = ?",
            (TASK_STATUS_RUNNING, _now(), task_id),
        )
        conn.commit()

    def mark_task_completed(self, task_id: str, *, result: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_tasks SET status = ?, result = ?, completed_at = ? WHERE task_id = ?",
            (TASK_STATUS_COMPLETED, result, _now(), task_id),
        )
        conn.commit()

    def mark_task_failed(self, task_id: str, *, error: str) -> None:
        conn = self._get_conn()
        conn.execute(
            "UPDATE team_tasks SET status = ?, error = ?, completed_at = ? WHERE task_id = ?",
            (TASK_STATUS_FAILED, error, _now(), task_id),
        )
        conn.commit()
