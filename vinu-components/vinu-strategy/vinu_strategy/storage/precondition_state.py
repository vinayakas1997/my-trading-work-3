"""Point 6's write-back path (missing-pieces-of-system/new-theory-of-
trading/system-wide-audit-and-design/reverse-engineering/
05-deciding-agent-and-precondition-tracking.md Part C): every time
`live_decision_agent` returns a real EXECUTE/SKIP decision for a
(ticker, strategy_id, trigger_id), that's a real check against real
evidence -- `tested` should flip to `true` (regardless of which way the
decision went; being checked and failing is still being tested), and
`precondition_held` should record that check's outcome.

Deliberately NOT written back into the strategy's own YAML file
(`vinu_strategy/engine/registry.py::StrategyRegistry`) -- that file is a
human-authored, declarative source of truth, reloaded on its own
schedule (`reload()`); a live process writing into it would blur config
(human-owned) with derived runtime state (system-owned), the exact
split `MetaStorage`/`WeightStorage` already draw for every other kind of
per-strategy state in this service. This is that same split applied to
`precondition`: a small, separate SQLite table, overlaid onto the
YAML-sourced `precondition` dict at read time
(`StrategyAPI.get_strategy()`), never mutating the file itself.

Keyed on `strategy_name` alone, not per-ticker -- `precondition` is a
property of the strategy's own definition ("what must be true before
this fires," per `03-strategy-definition-full-schema.md` item 4), not of
any one ticker it happens to be evaluated against, so one check on any
ticker is real evidence about the same claim.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

_SCHEMA = """
CREATE TABLE IF NOT EXISTS precondition_state (
    strategy_name      TEXT PRIMARY KEY,
    tested             INTEGER NOT NULL DEFAULT 0,
    precondition_held  INTEGER,
    last_checked_at    TEXT
);
"""


class PreconditionStateStore(SQLiteBackend):
    SCHEMA = _SCHEMA
    SCHEMA_VERSION = 1

    def __init__(self, path: Path | str) -> None:
        super().__init__(path)

    def record_check(
        self, strategy_name: str, *, precondition_held: bool | None, checked_at: str,
    ) -> None:
        """Upserted, not appended -- `tested`/`precondition_held` are a
        strategy's current state ("has this ever been checked, what did
        the most recent check find"), not a history table; the append-
        only audit trail of every individual check already lives in
        vinu-live's own `LiveDecisionRecord`/`live_decisions` table."""
        self.upsert(
            "precondition_state",
            {
                "strategy_name": strategy_name,
                "tested": 1,
                "precondition_held": None if precondition_held is None else int(precondition_held),
                "last_checked_at": checked_at,
            },
            conflict_columns=["strategy_name"],
        )

    def get(self, strategy_name: str) -> dict[str, Any] | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM precondition_state WHERE strategy_name=?", (strategy_name,),
        ).fetchone()
        if row is None:
            return None
        return {
            "tested": bool(row["tested"]),
            "precondition_held": None if row["precondition_held"] is None else bool(row["precondition_held"]),
            "last_checked_at": row["last_checked_at"],
        }
