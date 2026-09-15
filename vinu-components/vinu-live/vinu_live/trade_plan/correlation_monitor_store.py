"""Per-cycle history of `_check_runtime_correlation`'s own output
(orchestrator.py) -- that check has always recomputed pairwise correlation/
comovement fresh every cycle and returned it once in the cycle result, with
nothing kept across cycles: no way to see a pair's correlation climbing
over days, or audit which pairs were flagged but skipped a reduce due to
per-symbol cooldown. See the foundation-fixes audit in
missing-pieces-of-system/narating-agents/.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS correlation_monitor_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    checked_at    TEXT NOT NULL,
    n_flagged     INTEGER NOT NULL DEFAULT 0,
    flagged       TEXT NOT NULL DEFAULT '[]',
    reductions    TEXT NOT NULL DEFAULT '[]'
);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CorrelationMonitorEntry:
    checked_at: str
    n_flagged: int
    flagged: list[dict[str, Any]]
    reductions: list[dict[str, Any]]

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "CorrelationMonitorEntry":
        try:
            flagged = json.loads(row.get("flagged") or "[]")
        except Exception:
            flagged = []
        try:
            reductions = json.loads(row.get("reductions") or "[]")
        except Exception:
            reductions = []
        return cls(
            checked_at=row.get("checked_at", ""),
            n_flagged=int(row.get("n_flagged") or 0),
            flagged=flagged if isinstance(flagged, list) else [],
            reductions=reductions if isinstance(reductions, list) else [],
        )


class CorrelationMonitorStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record_cycle(
        self,
        n_flagged: int,
        flagged: list[dict[str, Any]],
        reductions: list[dict[str, Any]],
    ) -> None:
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO correlation_monitor_history (checked_at, n_flagged, flagged, reductions) "
            "VALUES (?, ?, ?, ?)",
            (_now(), n_flagged, json.dumps(flagged), json.dumps(reductions)),
        )
        conn.commit()

    def list_recent(self, limit: int = 100) -> list[CorrelationMonitorEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM correlation_monitor_history ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [CorrelationMonitorEntry.from_row(dict(r)) for r in rows]
