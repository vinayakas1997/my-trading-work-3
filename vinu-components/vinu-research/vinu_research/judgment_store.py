"""item #12 finding #1's "full fix": migrated onto SQLiteBackend, the
same shared pattern `hypothesis_registry.py`/`signal_evidence_store.py`/
`market_regime_history.py`/`strategy_store.py` already use for exactly
this "evidence-recording concern." Previously append-only JSONL with
**no lock at all** around the actual file write (`_persist()` ran
outside the one `threading.Lock()` this module did have, which only ever
protected the in-memory list) -- a real risk if this is ever written from
concurrent research loops, whether concurrent threads/tasks in one
process or, worse, multiple separate processes appending to the same
file. `SQLiteBackend`'s WAL-mode, thread-local connections replace the
raw JSONL append entirely; there's no separate in-memory copy to keep in
sync, so `load()` is now a real no-op (reads are always live).

`path=None` maps to SQLite's own `:memory:` special path, not a
hand-rolled parallel in-memory mode -- one real mechanism, not two. This
does mean a `path=None` store shared across multiple threads would see
one independent in-memory database per thread (`SQLiteBackend`'s own
thread-local connection model), same as any other `SQLiteBackend`
subclass used this way -- a real, documented limitation, not silently
different from every other store built on this same base class. Nothing
in this codebase currently constructs a `path=None` store and shares it
across threads (confirmed: zero real callers of this class exist yet at
all), so this is not a regression from today's actual behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend


@dataclass
class JudgmentRecord:
    ts: str
    symbol: str
    iteration: int
    verdict: str
    in_sample_sharpe: float
    out_of_sample_sharpe: float | None
    holdout_sharpe: float | None
    verdict_correct: bool | None
    llm_calls_used: int
    run_id: int = 0
    model: str = ""
    strategy_code_hash: str = ""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS judgments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    verdict TEXT NOT NULL,
    in_sample_sharpe REAL NOT NULL,
    out_of_sample_sharpe REAL,
    holdout_sharpe REAL,
    verdict_correct INTEGER,
    llm_calls_used INTEGER NOT NULL,
    run_id INTEGER NOT NULL DEFAULT 0,
    model TEXT NOT NULL DEFAULT '',
    strategy_code_hash TEXT NOT NULL DEFAULT ''
);
"""


class JudgmentStore(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str | None = None) -> None:
        super().__init__(path if path else ":memory:")

    def record(self, record: JudgmentRecord) -> None:
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO judgments
               (ts, symbol, iteration, verdict, in_sample_sharpe, out_of_sample_sharpe,
                holdout_sharpe, verdict_correct, llm_calls_used, run_id, model, strategy_code_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.ts, record.symbol, record.iteration, record.verdict,
                record.in_sample_sharpe, record.out_of_sample_sharpe, record.holdout_sharpe,
                None if record.verdict_correct is None else int(record.verdict_correct),
                record.llm_calls_used, record.run_id, record.model, record.strategy_code_hash,
            ),
        )
        conn.commit()

    def load(self) -> None:
        """No-op: reads are always live off the real connection now, same
        as every other SQLiteBackend subclass -- kept only so an existing
        caller of the old JSONL-era API doesn't break."""

    @property
    def total_records(self) -> int:
        conn = self._get_conn()
        return conn.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]

    def calibration_summary(self) -> dict[str, Any]:
        conn = self._get_conn()
        rows = conn.execute("SELECT verdict, verdict_correct FROM judgments").fetchall()
        total = len(rows)
        with_outcome = sum(1 for r in rows if r["verdict_correct"] is not None)

        by_verdict: dict[str, list[bool]] = {}
        for r in rows:
            if r["verdict_correct"] is not None:
                by_verdict.setdefault(r["verdict"], []).append(bool(r["verdict_correct"]))

        accuracies: dict[str, dict[str, Any]] = {}
        for verdict, outcomes in by_verdict.items():
            correct = sum(1 for o in outcomes if o)
            n = len(outcomes)
            accuracies[verdict] = {
                "count": n,
                "correct": correct,
                "accuracy": round(correct / n, 3) if n > 0 else 0.0,
            }

        return {"total": total, "with_outcome": with_outcome, "by_verdict": accuracies}

    def reset(self) -> None:
        conn = self._get_conn()
        conn.execute("DELETE FROM judgments")
        conn.commit()
