"""Rank-churn detection: which symbols entered or exited a ranker's top-N
between two consecutive rankings. The signal the user actually asked for
-- "yesterday AAPL was in the top 20, today it's not; why, and should that
stop something downstream" -- didn't exist before this, because
`RankedSnapshotStore` only ever kept the *latest* result, overwriting the
previous one with nothing to diff against.

`diff_rankings()` is pure and side-effect-free (easy to test in isolation);
`RankerChurnStore` is the permanent, queryable history of every event it
produces -- same "append-only audit table" convention as B17's
`WatchAuditStore`, applied to ranking instead of condition fires. A
symbol's churn history is meant to outlive any single snapshot, the same
way a fired-watch history outlives the live cooldown state that produced
it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from vinu_infra.sqlite import SQLiteBackend

from .snapshot_store import RankedSnapshotStore, RankerSnapshot

if TYPE_CHECKING:
    from ..pipeline.pipeline import PipelineResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS ranker_churn_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ranker_id  TEXT NOT NULL,
    symbol     TEXT NOT NULL,
    kind       TEXT NOT NULL,   -- "entered" | "exited"
    at         REAL NOT NULL,
    from_rank  INTEGER,
    to_rank    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_ranker_churn_ranker ON ranker_churn_events(ranker_id, at);
"""


@dataclass(frozen=True)
class ChurnEvent:
    ranker_id: str
    symbol: str
    kind: str                      # "entered" | "exited"
    at: float
    from_rank: int | None = None   # 1-based position in the PREVIOUS top-N, set only for "exited"
    to_rank: int | None = None     # 1-based position in the CURRENT top-N, set only for "entered"

    def to_dict(self) -> dict:
        return {
            "ranker_id": self.ranker_id, "symbol": self.symbol, "kind": self.kind,
            "at": self.at, "from_rank": self.from_rank, "to_rank": self.to_rank,
        }


def diff_rankings(
    ranker_id: str,
    previous_symbols: list[str] | None,
    current_symbols: list[str],
    *,
    now: float,
) -> list[ChurnEvent]:
    """`previous_symbols=None` means there's no prior ranking to diff
    against (the very first run of this ranker) -- deliberately produces
    NO events in that case. Every symbol in a first ranking is technically
    "new," but that's not a churn signal; it's just the ranker starting to
    exist. Churn only means something relative to a real prior state."""
    if previous_symbols is None:
        return []

    prev_rank = {symbol: i + 1 for i, symbol in enumerate(previous_symbols)}
    curr_rank = {symbol: i + 1 for i, symbol in enumerate(current_symbols)}

    events: list[ChurnEvent] = []
    for symbol, rank in curr_rank.items():
        if symbol not in prev_rank:
            events.append(ChurnEvent(ranker_id, symbol, "entered", now, to_rank=rank))
    for symbol, rank in prev_rank.items():
        if symbol not in curr_rank:
            events.append(ChurnEvent(ranker_id, symbol, "exited", now, from_rank=rank))
    return events


def record_ranking(
    snapshot_store: RankedSnapshotStore,
    churn_store: "RankerChurnStore | None",
    ranker_id: str,
    result: "PipelineResult",
    *,
    now: float,
) -> tuple[RankerSnapshot, list[ChurnEvent]]:
    """The one shared path both `RankerScheduler.tick()` and the on-demand
    `POST /screener/rankers/{id}/rank` route call -- reads the PREVIOUS
    latest snapshot before overwriting it (so the diff is always against
    genuinely the prior state, whether this ranking came from a scheduled
    tick or a manual re-run), persists the new one, diffs, and records the
    resulting events. Keeping this in one function is what guarantees an
    on-demand rank can't create a gap or a double-count in the churn
    history relative to the scheduled runs."""
    previous = snapshot_store.get_latest(ranker_id)
    previous_symbols = [c.symbol for c in previous.top] if previous is not None else None

    snapshot = snapshot_store.set_latest(ranker_id, result, now=now)
    current_symbols = [c.symbol for c in snapshot.top]

    events = diff_rankings(ranker_id, previous_symbols, current_symbols, now=now)
    if churn_store is not None and events:
        churn_store.record(events)
    return snapshot, events


class RankerChurnStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def record(self, events: list[ChurnEvent]) -> None:
        if not events:
            return
        conn = self._get_conn()
        conn.executemany(
            "INSERT INTO ranker_churn_events (ranker_id, symbol, kind, at, from_rank, to_rank) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(e.ranker_id, e.symbol, e.kind, e.at, e.from_rank, e.to_rank) for e in events],
        )
        conn.commit()

    def history(self, ranker_id: str, *, symbol: str | None = None, limit: int = 100) -> list[ChurnEvent]:
        conn = self._get_conn()
        if symbol is not None:
            rows = conn.execute(
                "SELECT ranker_id, symbol, kind, at, from_rank, to_rank FROM ranker_churn_events "
                "WHERE ranker_id = ? AND symbol = ? ORDER BY at DESC LIMIT ?",
                (ranker_id, symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ranker_id, symbol, kind, at, from_rank, to_rank FROM ranker_churn_events "
                "WHERE ranker_id = ? ORDER BY at DESC LIMIT ?",
                (ranker_id, limit),
            ).fetchall()
        return [ChurnEvent(r[0], r[1], r[2], float(r[3]), r[4], r[5]) for r in rows]
