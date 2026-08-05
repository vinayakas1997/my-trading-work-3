"""Shared per-LLM-call and per-pipeline-step telemetry, queryable via SQL.

Built for 05-advanced-aim-1-1's observability gap: 04-advanced-aim-1's real
22-day replay found the agent's context/tokenizer mismatch, retry counts,
and per-day tool-call failures only by manually re-reading raw JSON traces
after the fact — nothing was actually measuring this while it ran. This
module is the layer that would have surfaced it live instead.

Usage:
    from vinu_lib.telemetry import LLMCallRecord, record_llm_call_safe

    record_llm_call_safe(
        LLMCallRecord(
            service="vinu-agent", model="qwen36-35B", base_url="http://...",
            prompt_tokens=1200, completion_tokens=340, total_tokens=1540,
            token_count_source="provider", retry_count=1, latency_sec=4.2,
            success=True, outcome="completed",
        ),
        db_path="/data/telemetry.db",
    )

Deliberately additive, not a replacement for `vinu_lib.llm.client`'s existing
`data/llm_calls.jsonl` append log or `CostTracker` — this is a second,
queryable sink for the same class of event, plus a new one (`StepRecord`)
for non-LLM pipeline steps and tool calls that nothing previously recorded
at all.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_lib.sqlite import SQLiteBackend


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LLMCallRecord:
    """One LLM call. `token_count_source` distinguishes a real count the
    provider/server returned ("provider") from a fallback character-count
    heuristic ("estimated") — never present the two with the same
    confidence, same discipline as this project's freshness/facts work."""

    service: str
    model: str
    base_url: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    token_count_source: str  # "provider" | "estimated"
    retry_count: int
    latency_sec: float
    success: bool
    outcome: str  # e.g. "completed", "error", "timeout", "context_exceeded"
    error: str = ""
    ts: str = field(default_factory=_now_iso)


@dataclass
class StepRecord:
    """One pipeline step or tool call — anything that isn't itself an LLM
    call but is worth timing/counting: a tool invocation, a backfill run, a
    scheduled scan. `outcome` should be an explicit reason code
    ("completed", "hit_iteration_limit", "tool_error", "timeout", ...), not
    just success/failure, per 05-advanced-aim-1-1/AGENTS.md's design
    decision #1 — a step can fail to produce a real result without raising
    an exception, and that has to be visible here too."""

    service: str
    step_name: str
    duration_sec: float
    success: bool
    outcome: str
    data_volume_in: int = 0
    data_volume_out: int = 0
    error: str = ""
    ts: str = field(default_factory=_now_iso)


class TelemetryStore(SQLiteBackend):
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS llm_calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        service TEXT NOT NULL,
        model TEXT NOT NULL,
        base_url TEXT NOT NULL,
        prompt_tokens INTEGER NOT NULL,
        completion_tokens INTEGER NOT NULL,
        total_tokens INTEGER NOT NULL,
        token_count_source TEXT NOT NULL,
        retry_count INTEGER NOT NULL,
        latency_sec REAL NOT NULL,
        success INTEGER NOT NULL,
        outcome TEXT NOT NULL,
        error TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts);
    CREATE INDEX IF NOT EXISTS idx_llm_calls_service ON llm_calls(service);

    CREATE TABLE IF NOT EXISTS steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL,
        service TEXT NOT NULL,
        step_name TEXT NOT NULL,
        duration_sec REAL NOT NULL,
        success INTEGER NOT NULL,
        outcome TEXT NOT NULL,
        data_volume_in INTEGER NOT NULL DEFAULT 0,
        data_volume_out INTEGER NOT NULL DEFAULT 0,
        error TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_steps_ts ON steps(ts);
    CREATE INDEX IF NOT EXISTS idx_steps_service ON steps(service);
    """
    SCHEMA_VERSION = 1

    def record_llm_call(self, record: LLMCallRecord) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO llm_calls (ts, service, model, base_url, prompt_tokens, "
            "completion_tokens, total_tokens, token_count_source, retry_count, "
            "latency_sec, success, outcome, error) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                record.ts, record.service, record.model, record.base_url,
                record.prompt_tokens, record.completion_tokens, record.total_tokens,
                record.token_count_source, record.retry_count, record.latency_sec,
                int(record.success), record.outcome, record.error,
            ),
        )
        conn.commit()

    def record_step(self, record: StepRecord) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO steps (ts, service, step_name, duration_sec, success, "
            "outcome, data_volume_in, data_volume_out, error) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                record.ts, record.service, record.step_name, record.duration_sec,
                int(record.success), record.outcome, record.data_volume_in,
                record.data_volume_out, record.error,
            ),
        )
        conn.commit()

    def recent_llm_calls(self, limit: int = 100, service: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if service:
            rows = conn.execute(
                "SELECT * FROM llm_calls WHERE service=? ORDER BY id DESC LIMIT ?",
                (service, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM llm_calls ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def recent_steps(self, limit: int = 100, service: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if service:
            rows = conn.execute(
                "SELECT * FROM steps WHERE service=? ORDER BY id DESC LIMIT ?",
                (service, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM steps ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def summary(self, service: str | None = None) -> dict[str, Any]:
        """Cheap aggregate view — total calls/tokens/retries, steps by outcome
        — enough to answer "is anything obviously wrong" without a full
        table dump."""
        conn = self._get_conn()
        where = "WHERE service=?" if service else ""
        params = (service,) if service else ()
        call_row = conn.execute(
            f"SELECT COUNT(*) AS n, COALESCE(SUM(total_tokens),0) AS tokens, "
            f"COALESCE(SUM(retry_count),0) AS retries, "
            f"COALESCE(SUM(CASE WHEN success=0 THEN 1 ELSE 0 END),0) AS failures "
            f"FROM llm_calls {where}",
            params,
        ).fetchone()
        step_rows = conn.execute(
            f"SELECT outcome, COUNT(*) AS n FROM steps {where} GROUP BY outcome",
            params,
        ).fetchall()
        return {
            "llm_calls": dict(call_row),
            "steps_by_outcome": {r["outcome"]: r["n"] for r in step_rows},
        }


_stores: dict[str, TelemetryStore] = {}
_stores_lock = threading.Lock()


def get_telemetry_store(db_path: str | Path) -> TelemetryStore:
    """One store per resolved path, cached — never a single implicit-location
    singleton (that class of bug, a wrong/relative default data path silently
    landing somewhere unexpected, is exactly what
    `bugs-fixes-while-test/data-root-docker-path-mismatch.md` already found
    elsewhere in this project). Callers must pass their own real data root;
    there is no cwd-relative fallback here."""
    key = str(Path(db_path).resolve())
    store = _stores.get(key)
    if store is None:
        with _stores_lock:
            store = _stores.get(key)
            if store is None:
                store = TelemetryStore(key)
                _stores[key] = store
    return store


def record_llm_call_safe(record: LLMCallRecord, db_path: str | Path) -> None:
    """Best-effort write — telemetry must never break the caller's real
    request path. Mirrors this project's established pattern (e.g.
    `session/service.py`'s debrief-detector call, wrapped in
    `try/except: pass`) of never letting an observability side-effect take
    down the thing it's observing."""
    try:
        get_telemetry_store(db_path).record_llm_call(record)
    except Exception:
        pass


def record_step_safe(record: StepRecord, db_path: str | Path) -> None:
    try:
        get_telemetry_store(db_path).record_step(record)
    except Exception:
        pass
