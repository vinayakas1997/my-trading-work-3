"""Persists the *latest* ranked result per ranker, so `GET .../latest`
can be a cheap read instead of re-running the whole pipeline on every
request -- the ranker equivalent of B20's `PairlistCache`, but a durable
row instead of an in-process TTL cache, since a ranker's own schedule (as
infrequent as once a day) already controls freshness; there's nothing for
an additional in-process cache layer to add here.
"""

from __future__ import annotations

import dataclasses
import json
import time
from dataclasses import dataclass, field

from vinu_infra.sqlite import SQLiteBackend

from ..pipeline.pipeline import PipelineResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS ranker_snapshots (
    ranker_id    TEXT PRIMARY KEY,
    generated_at REAL NOT NULL,
    top_json     TEXT NOT NULL
);
"""

MIGRATIONS = [
    (
        "ALTER TABLE ranker_snapshots ADD COLUMN trace_json TEXT NOT NULL DEFAULT '[]'",
        "per-filter-stage before/after counts (PipelineResult.trace) -- "
        "computed on every run but previously dropped before reaching this "
        "store or the on-demand rank_now() response.",
    ),
]


@dataclass(frozen=True)
class RankedCandidate:
    symbol: str
    factor_score: float
    risk_penalty: float
    concentration_penalty: float
    final_score: float
    risk_flags: list[str]
    # Raw indicator values behind the score (price, volume, rsi, whatever
    # FactorSpecs this ranker computed) -- persisted so a consumer (the
    # Telegram /rank command, say) can show "RSI 28, vol 4.2M" per row
    # instead of just an opaque final_score. Candidate.fields already has
    # these; the pipeline just never used to carry them past this point.
    fields: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class RankerSnapshot:
    ranker_id: str
    generated_at: float
    top: list[RankedCandidate]
    # Per-filter-stage before/after counts (see StageCount, pipeline/
    # rule_filters.py) -- the "why did 500 tickers become 12" signal,
    # computed by ScreenPipeline.run() on every ranking but previously
    # dropped between there and here.
    trace: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ranker_id": self.ranker_id,
            "generated_at": self.generated_at,
            "top": [
                {
                    "symbol": c.symbol, "factor_score": c.factor_score, "risk_penalty": c.risk_penalty,
                    "concentration_penalty": c.concentration_penalty, "final_score": c.final_score,
                    "risk_flags": c.risk_flags, "fields": c.fields,
                }
                for c in self.top
            ],
            "trace": self.trace,
        }


class RankedSnapshotStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 2
    MIGRATIONS = MIGRATIONS

    def set_latest(self, ranker_id: str, result: PipelineResult, *, now: float | None = None) -> RankerSnapshot:
        now = now if now is not None else time.time()
        top = [
            RankedCandidate(
                c.symbol, c.factor_score, c.risk_penalty, c.concentration_penalty, c.final_score,
                list(c.risk_flags), dict(c.fields),
            )
            for c in result.top
        ]
        trace = [dataclasses.asdict(sc) for sc in result.trace]
        snapshot = RankerSnapshot(ranker_id, now, top, trace)
        self.upsert(
            "ranker_snapshots",
            {
                "ranker_id": ranker_id, "generated_at": now,
                "top_json": json.dumps(snapshot.to_dict()["top"]),
                "trace_json": json.dumps(trace),
            },
            conflict_columns=["ranker_id"],
        )
        return snapshot

    def get_latest(self, ranker_id: str) -> RankerSnapshot | None:
        row = self._get_conn().execute(
            "SELECT * FROM ranker_snapshots WHERE ranker_id = ?", (ranker_id,),
        ).fetchone()
        if row is None:
            return None
        top = [
            RankedCandidate(
                t["symbol"], t["factor_score"], t["risk_penalty"], t["concentration_penalty"], t["final_score"],
                t["risk_flags"], t.get("fields", {}),  # .get: tolerate snapshots written before `fields` existed
            )
            for t in json.loads(row["top_json"])
        ]
        # .keys() check: tolerate snapshots written before `trace_json` existed
        # (pre-migration rows on an already-running instance mid-upgrade).
        try:
            trace = json.loads(row["trace_json"]) if "trace_json" in row.keys() and row["trace_json"] else []
        except Exception:
            trace = []
        return RankerSnapshot(row["ranker_id"], float(row["generated_at"]), top, trace)
