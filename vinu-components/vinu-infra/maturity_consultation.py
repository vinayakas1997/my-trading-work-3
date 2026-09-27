"""Shared "who consulted the system maturity tier, and what did they do
about it" log -- system-wide-audit-and-design's high-expectations
follow-up (points #2/#3 of the maturity-agentic-system's own step-3
phasing: risk_gatekeeper and live_decision consulting the tier, both
still "not started" per that doc's own status section until now).

One shared table across every consumer/service, not one log per
consumer, so "what has the maturity tier actually influenced, system-
wide" is a single query away rather than scattered across services --
the same "one queryable place" reasoning `StrategyEvaluationStore`
already established for gate verdicts. Lives in vinu-infra because both
`vinu-live` (risk_gatekeeper, live_decision) and any future consumer
need to write to it, and neither should depend on the other's package to
do so.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS maturity_consultations (
    consultation_id TEXT PRIMARY KEY,
    consulted_at    REAL NOT NULL,
    service         TEXT NOT NULL,
    consumer        TEXT NOT NULL,
    scope_key       TEXT NOT NULL DEFAULT '',
    tier            TEXT NOT NULL,
    action_taken    TEXT NOT NULL,
    evidence_json   TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_maturity_consultations_consumer
    ON maturity_consultations(consumer, consulted_at);
CREATE INDEX IF NOT EXISTS idx_maturity_consultations_scope
    ON maturity_consultations(scope_key, consulted_at);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


class MaturityConsultationStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record(
        self,
        *,
        service: str,
        consumer: str,
        tier: str,
        action_taken: str,
        scope_key: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> str:
        """`action_taken` is a short, human-readable description of what
        actually happened as a result of this consultation (e.g.
        "limits_scaled_0.4x", "extra_confirmation_required",
        "no_change_already_mature") -- always recorded, even when the
        tier didn't end up changing anything, so "did this ever actually
        do anything" is answerable from the log alone."""
        consultation_id = uuid.uuid4().hex[:16]
        self.upsert(
            "maturity_consultations",
            {
                "consultation_id": consultation_id,
                "consulted_at": time.time(),
                "service": service,
                "consumer": consumer,
                "scope_key": scope_key,
                "tier": tier,
                "action_taken": action_taken,
                "evidence_json": json.dumps(evidence or {}, default=str),
            },
            conflict_columns=["consultation_id"],
        )
        return consultation_id

    def list_recent(
        self, consumer: Optional[str] = None, limit: int = 50,
    ) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if consumer:
            rows = conn.execute(
                "SELECT * FROM maturity_consultations WHERE consumer = ? "
                "ORDER BY consulted_at DESC LIMIT ?",
                (consumer, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM maturity_consultations ORDER BY consulted_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["evidence"] = json.loads(d.pop("evidence_json") or "{}")
            result.append(d)
        return result
