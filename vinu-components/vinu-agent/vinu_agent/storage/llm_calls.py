"""Every-LLM-call log: full prompt, response, token usage, and latency for
every single call made anywhere in vinu-agent (orchestrator, every team
manager, every specialist) -- so context usage can be inspected after the
fact, call by call, not just as aggregate counts.

See New-talk-agents/01-orchestrator-and-teams-architecture.md and
New-talk-agents/implementation/00-status.md.
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
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id                   TEXT PRIMARY KEY,
    created_at                 TEXT NOT NULL,
    service                    TEXT NOT NULL DEFAULT '',
    tier                       TEXT NOT NULL DEFAULT '',
    team                       TEXT NOT NULL DEFAULT '',
    agent                      TEXT NOT NULL DEFAULT '',
    role                       TEXT NOT NULL DEFAULT '',
    session_id                 TEXT NOT NULL DEFAULT '',
    provider                   TEXT NOT NULL DEFAULT '',
    model                      TEXT NOT NULL DEFAULT '',
    base_url                   TEXT NOT NULL DEFAULT '',
    prompt_json                TEXT NOT NULL DEFAULT '[]',
    tools_json                 TEXT NOT NULL DEFAULT '[]',
    response_content           TEXT NOT NULL DEFAULT '',
    response_tool_calls_json   TEXT NOT NULL DEFAULT '[]',
    prompt_tokens              INTEGER NOT NULL DEFAULT 0,
    completion_tokens          INTEGER NOT NULL DEFAULT 0,
    total_tokens               INTEGER NOT NULL DEFAULT 0,
    token_count_source         TEXT NOT NULL DEFAULT '',
    retry_count                INTEGER NOT NULL DEFAULT 0,
    latency_sec                REAL NOT NULL DEFAULT 0.0,
    success                    INTEGER NOT NULL DEFAULT 1,
    error                      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_llm_calls_created_at ON llm_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_llm_calls_tier ON llm_calls(tier);
CREATE INDEX IF NOT EXISTS idx_llm_calls_session ON llm_calls(session_id);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class LlmCallRecord:
    call_id: str = field(default_factory=_new_id)
    created_at: str = field(default_factory=_now)
    service: str = ""
    tier: str = ""
    team: str = ""
    agent: str = ""
    role: str = ""
    session_id: str = ""
    provider: str = ""
    model: str = ""
    base_url: str = ""
    prompt: list[dict[str, Any]] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    response_content: str = ""
    response_tool_calls: list[dict[str, Any]] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    token_count_source: str = ""
    retry_count: int = 0
    latency_sec: float = 0.0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["prompt_json"] = json.dumps(d.pop("prompt"))
        d["tools_json"] = json.dumps(d.pop("tools"))
        d["response_tool_calls_json"] = json.dumps(d.pop("response_tool_calls"))
        d["success"] = 1 if d["success"] else 0
        return d

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "LlmCallRecord":
        def _loads(key: str) -> list:
            raw = row.get(key, "[]")
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return []
            return raw or []

        return cls(
            call_id=row["call_id"],
            created_at=row.get("created_at", ""),
            service=row.get("service", ""),
            tier=row.get("tier", ""),
            team=row.get("team", ""),
            agent=row.get("agent", ""),
            role=row.get("role", ""),
            session_id=row.get("session_id", ""),
            provider=row.get("provider", ""),
            model=row.get("model", ""),
            base_url=row.get("base_url", ""),
            prompt=_loads("prompt_json"),
            tools=_loads("tools_json"),
            response_content=row.get("response_content", ""),
            response_tool_calls=_loads("response_tool_calls_json"),
            prompt_tokens=int(row.get("prompt_tokens") or 0),
            completion_tokens=int(row.get("completion_tokens") or 0),
            total_tokens=int(row.get("total_tokens") or 0),
            token_count_source=row.get("token_count_source", ""),
            retry_count=int(row.get("retry_count") or 0),
            latency_sec=float(row.get("latency_sec") or 0.0),
            success=bool(row.get("success", 1)),
            error=row.get("error", ""),
        )


class LlmCallLogStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record(self, call: LlmCallRecord) -> None:
        self.upsert("llm_calls", call.to_dict(), conflict_columns=["call_id"])

    def get_call(self, call_id: str) -> Optional[LlmCallRecord]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM llm_calls WHERE call_id = ?", (call_id,)).fetchone()
        if row is None:
            return None
        return LlmCallRecord.from_row(dict(row))

    def list_calls(
        self,
        *,
        tier: Optional[str] = None,
        team: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 100,
    ) -> list[LlmCallRecord]:
        conn = self._get_conn()
        conditions: list[str] = []
        params: list[Any] = []
        if tier:
            conditions.append("tier = ?")
            params.append(tier)
        if team:
            conditions.append("team = ?")
            params.append(team)
        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        rows = conn.execute(
            f"SELECT * FROM llm_calls {where} ORDER BY created_at DESC LIMIT ?", params,
        ).fetchall()
        return [LlmCallRecord.from_row(dict(r)) for r in rows]

    def total_tokens_by_tier(self) -> dict[str, int]:
        """Answers the actual question this store exists for: how much
        context is each tier (orchestrator/manager/specialist) actually
        using, in aggregate."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT tier, SUM(total_tokens) AS total FROM llm_calls GROUP BY tier"
        ).fetchall()
        return {r["tier"]: int(r["total"] or 0) for r in rows}
