"""Shared "why was this rejected" shape -- item #21 pattern #3 (system-
wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
"compute why something failed, then discard it before persisting" is a
recurring habit across at least three unrelated components (item #3's
sweep comparison verdict, item #16.2's generation-time candidate scoring,
item #18.3's screener per-symbol reject reasons) -- independent
components converging on the same omission, the same shape pattern #2
(indicator duplication) already showed for computation logic.

Deliberately a pure dataclass + constructor, not a shared table: per this
finding's own text, "different components can each store rows in their
own existing storage, but all through the same write function/schema" --
this gives every consumer one shared shape to serialize into whatever
storage it already has (a JSON column, an existing SQLite table, ...)
rather than each one inventing its own ad hoc reason-string convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class RejectionRecord:
    # "sweep_run" | "generation_candidate" | "screener_symbol", or a new
    # value a future consumer adds -- deliberately not a closed enum, so
    # adopting this shape never requires a change here first.
    entity_type: str
    entity_id: str
    stage: str
    rejection_category: str
    rejection_detail: str
    compared_against_id: str | None = None
    timestamp: str = ""

    def to_dict(self) -> dict[str, str | None]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "stage": self.stage,
            "rejection_category": self.rejection_category,
            "rejection_detail": self.rejection_detail,
            "compared_against_id": self.compared_against_id,
            "timestamp": self.timestamp,
        }


def record_rejection(
    entity_type: str,
    entity_id: str,
    stage: str,
    rejection_category: str,
    rejection_detail: str,
    *,
    compared_against_id: str | None = None,
    timestamp: str | None = None,
) -> RejectionRecord:
    """Builds one `RejectionRecord`. Pure -- callers decide where it lands
    (append to a bounded in-memory sample, write a JSON column, insert a
    row in an existing table); this function only fixes the shape and the
    timestamp convention (UTC ISO-8601, matching this codebase's existing
    point-in-time discipline) so three independent write sites don't each
    pick a different one."""
    return RejectionRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        stage=stage,
        rejection_category=rejection_category,
        rejection_detail=rejection_detail,
        compared_against_id=compared_against_id,
        timestamp=timestamp if timestamp is not None else datetime.now(timezone.utc).isoformat(),
    )
