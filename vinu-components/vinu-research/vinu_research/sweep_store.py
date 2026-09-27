"""item #3 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): individual sweep-candidate
runs are already durably persisted by `vinu-simulator`'s own
`simulation_runs` table -- what's missing is the *comparison itself*.
`SweepGridResult` (`sweep_grid.py`) is a plain in-memory dataclass;
`routes_sweep.py` serializes it straight into an HTTP response and
nothing writes it down. Today 20 sweep runs sit in `simulation_runs`
looking like 20 unrelated ad-hoc backtests -- nothing on disk records
that they were one search round, what rank each got, or why the others
lost.

Additive, not a redesign, exactly as this finding's own text specifies:
one grouping table keyed by a new `sweep_id`, written at the exact point
`run_sweep_grid()` already builds its in-memory result -- the data
already exists, it's just never written down. Also closes item #12
finding #4 (the walk-forward result nested in this same discarded
object) by persisting `SweepGridResult.walk_forward` on the same header
row, not as a separate mechanism.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sweep_runs (
    sweep_id          TEXT PRIMARY KEY,
    symbol            TEXT NOT NULL,
    from_date         TEXT NOT NULL,
    to_date           TEXT NOT NULL,
    requested         INTEGER NOT NULL,
    succeeded         INTEGER NOT NULL,
    completeness      REAL NOT NULL,
    pbo_json          TEXT,
    walk_forward_json TEXT,
    created_at        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sweep_grid_points (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sweep_id         TEXT NOT NULL,
    run_id           TEXT,
    rank             INTEGER,
    score            REAL,
    risk_score       REAL,
    complexity_score REAL,
    succeeded        INTEGER NOT NULL,
    failure_reason   TEXT NOT NULL DEFAULT '',
    params_json      TEXT NOT NULL,
    created_at       REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sweep_grid_points_sweep_id ON sweep_grid_points(sweep_id);
"""


class SweepGridStore(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str | None = None) -> None:
        super().__init__(path if path else ":memory:")

    def record_sweep(
        self,
        sweep_id: str,
        *,
        symbol: str,
        from_date: str,
        to_date: str,
        result: Any,
        now: float | None = None,
    ) -> None:
        """`result` is a `sweep_grid.SweepGridResult` -- typed as `Any`
        here to avoid a circular import (`sweep_grid.py` calls this
        module, not the other way around)."""
        now = now if now is not None else time.time()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO sweep_runs
               (sweep_id, symbol, from_date, to_date, requested, succeeded,
                completeness, pbo_json, walk_forward_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                sweep_id, symbol, from_date, to_date, result.requested, result.succeeded,
                result.completeness,
                json.dumps(result.pbo) if result.pbo is not None else None,
                json.dumps(result.walk_forward) if result.walk_forward is not None else None,
                now,
            ),
        )
        # rank is 1-indexed (rank 1 = the winner) -- result.ranked is
        # already best-first (comparison.rank_candidates), matching the
        # vocabulary a human reading this table would expect.
        for i, r in enumerate(result.ranked):
            conn.execute(
                """INSERT INTO sweep_grid_points
                   (sweep_id, run_id, rank, score, risk_score, complexity_score,
                    succeeded, failure_reason, params_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, 1, '', ?, ?)""",
                (
                    sweep_id, r.sweep_result.run_id, i + 1, r.score, r.risk_score,
                    r.complexity_score, json.dumps(r.params), now,
                ),
            )
        for o in result.outcomes:
            if o.succeeded:
                continue  # already recorded above via result.ranked
            conn.execute(
                """INSERT INTO sweep_grid_points
                   (sweep_id, run_id, rank, score, risk_score, complexity_score,
                    succeeded, failure_reason, params_json, created_at)
                   VALUES (?, NULL, NULL, NULL, NULL, NULL, 0, ?, ?, ?)""",
                (sweep_id, o.error, json.dumps(o.params), now),
            )
        conn.commit()

    def get_sweep(self, sweep_id: str) -> dict[str, Any] | None:
        """The full "why this lost" picture for one search round: the
        header (aggregate completeness/PBO/walk-forward verdict) plus
        every point that was tried, winner and losers alike, in rank
        order (failed points last, `rank` NULL)."""
        conn = self._get_conn()
        header = conn.execute("SELECT * FROM sweep_runs WHERE sweep_id = ?", (sweep_id,)).fetchone()
        if header is None:
            return None
        points = conn.execute(
            "SELECT * FROM sweep_grid_points WHERE sweep_id = ? "
            "ORDER BY (rank IS NULL), rank ASC",
            (sweep_id,),
        ).fetchall()
        return {
            "sweep_id": header["sweep_id"],
            "symbol": header["symbol"],
            "from_date": header["from_date"],
            "to_date": header["to_date"],
            "requested": header["requested"],
            "succeeded": header["succeeded"],
            "completeness": header["completeness"],
            "pbo": json.loads(header["pbo_json"]) if header["pbo_json"] else None,
            "walk_forward": json.loads(header["walk_forward_json"]) if header["walk_forward_json"] else None,
            "created_at": header["created_at"],
            "points": [
                {
                    "run_id": p["run_id"],
                    "rank": p["rank"],
                    "score": p["score"],
                    "risk_score": p["risk_score"],
                    "complexity_score": p["complexity_score"],
                    "succeeded": bool(p["succeeded"]),
                    "failure_reason": p["failure_reason"],
                    "params": json.loads(p["params_json"]),
                }
                for p in points
            ],
        }

    def list_sweeps(self, *, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        """Header rows only, most recent first -- "has a search round like
        this already been tried" without pulling every point of every
        sweep. The `symbol` filter is a real SQL WHERE (not
        item #13 finding #3's own load-everything-then-filter-in-Python
        mistake, avoided here from the start)."""
        conn = self._get_conn()
        if symbol is not None:
            rows = conn.execute(
                "SELECT * FROM sweep_runs WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM sweep_runs ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [
            {
                "sweep_id": r["sweep_id"], "symbol": r["symbol"], "from_date": r["from_date"],
                "to_date": r["to_date"], "requested": r["requested"], "succeeded": r["succeeded"],
                "completeness": r["completeness"], "created_at": r["created_at"],
            }
            for r in rows
        ]
