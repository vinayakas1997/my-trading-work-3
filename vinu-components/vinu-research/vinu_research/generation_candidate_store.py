"""item #16 finding #2 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): "generation-time candidate
loss -- a new, earlier discard point than item #14's sweep-candidate
loss." `LlmStrategyGenerator.generate()`/`.refine()` draft several
candidates per call; `comparison.rank_candidates()` picks the best by a
heuristic complexity-penalty score (no backtest exists yet at this
point); the others are discarded immediately -- never recorded, never
backtested, and the ranking itself never checked against real outcomes.

Same shared `RejectionRecord` shape (`vinu_infra.rejection_log`) as
every other instance of this recurring pattern (items #3/#18.3/#21.3/
#23.5), but this is the one instance with genuinely no existing
persistence surface to extend -- unlike item #3's sweep-run table, there
was nothing here before. `find_by_code_hash` gives a first, deliberately
small answer to this item's own finding #3 ("a unified candidate
graveyard is needed") for exactly this one death point -- not the full
cross-death-point graveyard that finding describes, which stays a
separate, bigger decision.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

_SCHEMA = """
CREATE TABLE IF NOT EXISTS generation_rounds (
    generation_id TEXT PRIMARY KEY,
    symbol        TEXT NOT NULL,
    iteration     INTEGER NOT NULL,
    mode          TEXT NOT NULL,
    n_candidates  INTEGER NOT NULL,
    created_at    REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS generation_candidates (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id     TEXT NOT NULL,
    code_hash         TEXT NOT NULL,
    chosen            INTEGER NOT NULL,
    score             REAL NOT NULL,
    complexity_score  REAL NOT NULL,
    reasoning_excerpt TEXT NOT NULL DEFAULT '',
    created_at        REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generation_candidates_generation_id ON generation_candidates(generation_id);
CREATE INDEX IF NOT EXISTS idx_generation_candidates_code_hash ON generation_candidates(code_hash);
"""


def code_hash(code: str) -> str:
    """A stable identifier for a candidate with no other one -- LlmCandidate
    carries no id at all, only code/params/reasoning. Truncated to 16 hex
    chars: this is for "has something like this already been tried,"
    not a security context, so collision resistance beyond avoiding
    accidental clashes across a realistic number of rounds is not needed."""
    return hashlib.sha256((code or "").encode("utf-8")).hexdigest()[:16]


class GenerationCandidateStore(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str | None = None) -> None:
        super().__init__(path if path else ":memory:")

    def record_round(
        self,
        generation_id: str,
        *,
        symbol: str,
        iteration: int,
        mode: str,
        ranked: list[Any],
        now: float | None = None,
    ) -> None:
        """`ranked` is a `list[comparison.RankedCandidate]` -- typed `Any`
        to avoid a circular import (`comparison.py` doesn't import this
        module). Every candidate is recorded, winner included (`chosen`
        flag), not just the losers -- the winner is part of "why this
        round went the way it did" too, and this table is the only place
        that fact would otherwise live."""
        now = now if now is not None else time.time()
        conn = self._get_conn()
        conn.execute(
            """INSERT OR REPLACE INTO generation_rounds
               (generation_id, symbol, iteration, mode, n_candidates, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (generation_id, symbol, iteration, mode, len(ranked), now),
        )
        for i, r in enumerate(ranked):
            conn.execute(
                """INSERT INTO generation_candidates
                   (generation_id, code_hash, chosen, score, complexity_score,
                    reasoning_excerpt, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    generation_id, code_hash(r.candidate.code), 1 if i == 0 else 0,
                    r.score, r.complexity_score, (r.candidate.reasoning or "")[:200], now,
                ),
            )
        conn.commit()

    def get_round(self, generation_id: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        header = conn.execute(
            "SELECT * FROM generation_rounds WHERE generation_id = ?", (generation_id,),
        ).fetchone()
        if header is None:
            return None
        candidates = conn.execute(
            "SELECT * FROM generation_candidates WHERE generation_id = ? "
            "ORDER BY chosen DESC, score DESC",
            (generation_id,),
        ).fetchall()
        return {
            "generation_id": header["generation_id"],
            "symbol": header["symbol"],
            "iteration": header["iteration"],
            "mode": header["mode"],
            "n_candidates": header["n_candidates"],
            "created_at": header["created_at"],
            "candidates": [
                {
                    "code_hash": c["code_hash"],
                    "chosen": bool(c["chosen"]),
                    "score": c["score"],
                    "complexity_score": c["complexity_score"],
                    "reasoning_excerpt": c["reasoning_excerpt"],
                }
                for c in candidates
            ],
        }

    def list_rounds(self, *, symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if symbol is not None:
            rows = conn.execute(
                "SELECT * FROM generation_rounds WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM generation_rounds ORDER BY created_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [
            {
                "generation_id": r["generation_id"], "symbol": r["symbol"], "iteration": r["iteration"],
                "mode": r["mode"], "n_candidates": r["n_candidates"], "created_at": r["created_at"],
            }
            for r in rows
        ]

    def find_by_code_hash(self, hash_: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """item #16 finding #3's own "has something like this already
        failed, and why" question -- a first, narrow answer scoped to
        this one death point (generation-time), not the unified
        cross-death-point graveyard that finding describes as a bigger,
        separate decision."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM generation_candidates WHERE code_hash = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (hash_, limit),
        ).fetchall()
        return [
            {
                "generation_id": r["generation_id"], "chosen": bool(r["chosen"]),
                "score": r["score"], "complexity_score": r["complexity_score"],
                "reasoning_excerpt": r["reasoning_excerpt"], "created_at": r["created_at"],
            }
            for r in rows
        ]
