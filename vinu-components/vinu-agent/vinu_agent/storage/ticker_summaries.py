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

import json
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

SCHEMA_VERSION = 5
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
    (
        "ALTER TABLE ticker_summaries ADD COLUMN angle_digest TEXT NOT NULL DEFAULT '{}'",
        "structured per-angle digest (JSON) from build_angle_digest -- closes the "
        "gate-conflict gap where forecast_skill only ever saw 2 of ~28 angles as "
        "structured input, everything else discarded after computing counts.",
    ),
    (
        "ALTER TABLE ticker_summaries ADD COLUMN cluster_digest TEXT NOT NULL DEFAULT '{}'",
        "the 7-cluster synthesis (JSON, one entry per cluster A-G) angle_synthesizer's "
        "now-cluster-scoped delegations produce -- unlike angle_digest, this has no "
        "deterministic-Python equivalent (it's LLM reasoning, not a field copy), so it "
        "only exists in the screener manager's own JSON block. See "
        "missing-pieces-of-system/angle-comprehension-hierarchy/01-plan.md step 4.",
    ),
    (
        "ALTER TABLE ticker_summaries ADD COLUMN cross_cluster TEXT NOT NULL DEFAULT '{}'",
        "cross_cluster_analyst's ticker-level output (JSON: consensus_checks, "
        "calibration, corroborations, redundant_clusters) -- same LLM-only-source "
        "reasoning as cluster_digest, not deterministic.",
    ),
    (
        "ALTER TABLE ticker_summaries ADD COLUMN cluster_anomalies TEXT NOT NULL DEFAULT '{}'",
        "per-cluster anomaly lists (JSON: {cluster_letter: [anomaly, ...]}), kept "
        "SEPARATE from cluster_digest -- real finding (2026-09-22, live LLM test): a "
        "cluster's synthesis sentence can launder an anomalous value (e.g. a prompt-"
        "injection payload inside an angle field) into plausible-sounding market "
        "language without literally repeating it, so the anomalies list is what "
        "actually preserves the 'this was flagged' signal for forecast_skill to read.",
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
    angle_digest: dict[str, Any] = None  # type: ignore[assignment]
    cluster_digest: dict[str, Any] = None  # type: ignore[assignment]
    cross_cluster: dict[str, Any] = None  # type: ignore[assignment]
    cluster_anomalies: dict[str, Any] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.angle_digest is None:
            self.angle_digest = {}
        if self.cluster_digest is None:
            self.cluster_digest = {}
        if self.cross_cluster is None:
            self.cross_cluster = {}
        if self.cluster_anomalies is None:
            self.cluster_anomalies = {}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TickerSummary":
        def _load_dict(key: str) -> dict[str, Any]:
            try:
                value = json.loads(row.get(key) or "{}")
                return value if isinstance(value, dict) else {}
            except Exception:
                return {}

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
            angle_digest=_load_dict("angle_digest"),
            cluster_digest=_load_dict("cluster_digest"),
            cross_cluster=_load_dict("cross_cluster"),
            cluster_anomalies=_load_dict("cluster_anomalies"),
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
        angle_digest: dict[str, Any] | None = None,
        cluster_digest: dict[str, Any] | None = None,
        cross_cluster: dict[str, Any] | None = None,
        cluster_anomalies: dict[str, Any] | None = None,
    ) -> TickerSummary:
        ticker = ticker.upper()
        now = _now()
        existing = self.get_summary(ticker)
        created_at = existing.created_at if existing else now
        angle_digest = angle_digest or {}
        cluster_digest = cluster_digest or {}
        cross_cluster = cross_cluster or {}
        cluster_anomalies = cluster_anomalies or {}
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
                "angle_digest": json.dumps(angle_digest),
                "cluster_digest": json.dumps(cluster_digest),
                "cross_cluster": json.dumps(cross_cluster),
                "cluster_anomalies": json.dumps(cluster_anomalies),
            },
            conflict_columns=["ticker"],
        )
        return TickerSummary(
            ticker=ticker, summary=summary, angles_with_data=angles_with_data,
            angle_count=angle_count, source_run_id=source_run_id,
            created_at=created_at, updated_at=now, angle_digest=angle_digest,
            cluster_digest=cluster_digest, cross_cluster=cross_cluster,
            cluster_anomalies=cluster_anomalies,
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
