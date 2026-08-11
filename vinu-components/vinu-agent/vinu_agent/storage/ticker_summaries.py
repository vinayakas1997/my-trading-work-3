"""Per-ticker angle-synthesis summaries: the durable output of the
`screener` team's own job -- fetch every vinu-initial-analysis angle for
a ticker, have an LLM read all of it once, and keep the resulting
summary around so the next thing that needs "what does the data say
about this ticker" doesn't have to re-run the whole synthesis from
scratch. One row per ticker, overwritten (not versioned) on each new
screener run -- the point is "the latest read," not a history of every
past one; team_runs already keeps the full run history if that's ever
needed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_summaries (
    ticker              TEXT PRIMARY KEY,
    summary             TEXT NOT NULL DEFAULT '',
    angles_with_data    INTEGER NOT NULL DEFAULT 0,
    angle_count         INTEGER NOT NULL DEFAULT 0,
    source_run_id       TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_ticker_summaries_updated_at ON ticker_summaries(updated_at);
"""

SCHEMA_VERSION = 2
MIGRATIONS: list[tuple[str, str]] = [
    # Phase 0's change-gate (GATE) state: "what did the gate last see for
    # this ticker" -- kept as columns on the existing one-row-per-ticker
    # store rather than a new table, per
    # phases/phase-0-foundation-plumbing/01-plan.md. Distinct from
    # source_run_id above: source_run_id is "what the Summary Agent's
    # output is built from," last_checked_run_id/last_checked_artifact_
    # signature are "what the gate compared against last time" -- the same
    # value in practice right after a refresh, but conceptually different
    # fields that would diverge the moment the gate fires on an
    # artifact-status-only change (source_run_id doesn't move, but
    # last_checked_artifact_signature must).
    (
        "ALTER TABLE ticker_summaries ADD COLUMN last_checked_run_id TEXT NOT NULL DEFAULT ''",
        "phase-0 -- change-gate state, see phases/phase-0-foundation-plumbing/01-plan.md",
    ),
    (
        "ALTER TABLE ticker_summaries ADD COLUMN last_checked_artifact_signature TEXT NOT NULL DEFAULT ''",
        "phase-0 -- change-gate state, see phases/phase-0-foundation-plumbing/01-plan.md",
    ),
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class TickerSummary:
    ticker: str
    summary: str = ""
    angles_with_data: int = 0
    angle_count: int = 0
    source_run_id: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_checked_run_id: str = ""
    last_checked_artifact_signature: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TickerSummary":
        return cls(
            ticker=row["ticker"],
            summary=row.get("summary", ""),
            angles_with_data=int(row.get("angles_with_data") or 0),
            angle_count=int(row.get("angle_count") or 0),
            source_run_id=row.get("source_run_id", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            last_checked_run_id=row.get("last_checked_run_id", ""),
            last_checked_artifact_signature=row.get("last_checked_artifact_signature", ""),
        )


class TickerSummaryStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def upsert_summary(
        self,
        ticker: str,
        summary: str,
        *,
        angles_with_data: int = 0,
        angle_count: int = 0,
        source_run_id: str = "",
    ) -> TickerSummary:
        ticker = ticker.upper()
        now = _now()
        existing = self.get_summary(ticker)
        created_at = existing.created_at if existing else now
        self.upsert(
            "ticker_summaries",
            {
                "ticker": ticker,
                "summary": summary,
                "angles_with_data": angles_with_data,
                "angle_count": angle_count,
                "source_run_id": source_run_id,
                "created_at": created_at,
                "updated_at": now,
            },
            conflict_columns=["ticker"],
        )
        return TickerSummary(
            ticker=ticker, summary=summary, angles_with_data=angles_with_data,
            angle_count=angle_count, source_run_id=source_run_id,
            created_at=created_at, updated_at=now,
        )

    def get_summary(self, ticker: str) -> Optional[TickerSummary]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ticker_summaries WHERE ticker = ?", (ticker.upper(),)
        ).fetchone()
        return TickerSummary.from_row(dict(row)) if row else None

    def record_gate_check(
        self, ticker: str, *, run_id: str, artifact_signature: str
    ) -> None:
        """Phase 0's change-gate state update, called after a 'yes' pass so
        an immediate second check on the same, now-unchanged ticker returns
        'no'. Separate from upsert_summary -- this can fire on an
        artifact-status-only change where the Summary Agent never runs and
        source_run_id never moves; a plain upsert_summary call here would
        wrongly imply a new summary was written."""
        ticker = ticker.upper()
        now = _now()
        existing = self.get_summary(ticker)
        if existing is None:
            # No summary written for this ticker yet -- still record the
            # gate's own state so it doesn't loop re-fetching artifacts it
            # already saw. Leaves summary fields at their table defaults.
            self.upsert(
                "ticker_summaries",
                {
                    "ticker": ticker,
                    "last_checked_run_id": run_id,
                    "last_checked_artifact_signature": artifact_signature,
                    "created_at": now,
                    "updated_at": now,
                },
                conflict_columns=["ticker"],
            )
            return
        conn = self._get_conn()
        conn.execute(
            "UPDATE ticker_summaries SET last_checked_run_id = ?, "
            "last_checked_artifact_signature = ? WHERE ticker = ?",
            (run_id, artifact_signature, ticker),
        )
        conn.commit()

    def list_summaries(self) -> list[TickerSummary]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM ticker_summaries ORDER BY updated_at DESC"
        ).fetchall()
        return [TickerSummary.from_row(dict(r)) for r in rows]
