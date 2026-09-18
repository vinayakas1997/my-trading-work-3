"""New writer for 25-A-Y-details/04-decision-process-cognition.md's
analysis K ("does retrieved memory actually help"). Before this, the
`ContextBuilder.build_messages()` block that pulls facts/memory entries
formatted them straight into the prompt's free-text `user_message` --
no structured record of which specific `facts.id`/`memory_entries.id`
were actually selected was written anywhere. This is that record: one
row per `build_messages()` call, keyed by `session_id`, so K (or
anything else) can later join "did this session have relevant context
injected" against `team_runs.verdict` for the same `session_id`
(TeamRunStore.get_latest_verdict_by_session_id -- the same join key
analysis D already uses).
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS injected_context_log (
    id               TEXT PRIMARY KEY,
    session_id       TEXT NOT NULL DEFAULT '',
    created_at       TEXT NOT NULL,
    fact_ids_json    TEXT NOT NULL DEFAULT '[]',
    memory_ids_json  TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_injected_context_log_session ON injected_context_log(session_id);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class InjectedContextRecord:
    session_id: str
    fact_ids: list[str] = field(default_factory=list)
    memory_ids: list[str] = field(default_factory=list)
    id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "fact_ids_json": json.dumps(self.fact_ids),
            "memory_ids_json": json.dumps(self.memory_ids),
        }

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "InjectedContextRecord":
        def _loads(key: str) -> list[str]:
            raw = row.get(key, "[]")
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return []
            return raw or []

        return cls(
            id=row["id"],
            session_id=row.get("session_id", ""),
            created_at=row.get("created_at", ""),
            fact_ids=_loads("fact_ids_json"),
            memory_ids=_loads("memory_ids_json"),
        )


class InjectedContextLogStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record(self, session_id: str, *, fact_ids: list[str], memory_ids: list[str]) -> None:
        """Best-effort by design (mirrors telemetry.py's `record_llm_call_safe`
        posture): logging what was injected must never be able to break the
        real chat turn it's observing. Only actually writes a row when there
        was something to log at all -- a turn with no facts/memory hits
        doesn't need a row to prove "nothing was available"; K's Fetch
        compares against runs with no matching row just as well."""
        if not fact_ids and not memory_ids:
            return
        try:
            record = InjectedContextRecord(session_id=session_id, fact_ids=list(fact_ids), memory_ids=list(memory_ids))
            self.upsert("injected_context_log", record.to_dict(), conflict_columns=["id"])
        except Exception:
            pass

    def list_by_session_id(self, session_id: str) -> list[InjectedContextRecord]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM injected_context_log WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        ).fetchall()
        return [InjectedContextRecord.from_row(dict(r)) for r in rows]

    def distinct_session_ids(self) -> list[str]:
        """Every session that ever had at least one fact/memory injection
        logged -- what analysis K iterates the "had relevant context"
        side over."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT DISTINCT session_id FROM injected_context_log WHERE session_id != ''"
        ).fetchall()
        return [r["session_id"] for r in rows]
