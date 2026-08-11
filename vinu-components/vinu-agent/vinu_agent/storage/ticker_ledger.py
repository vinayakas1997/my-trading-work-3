"""TickerLedger: one row per ticker-relevant event across the whole
pipeline -- the narrative index of "everything that happened for AAPL, in
order." Never a duplicate copy of the real data; `ref_id` points at the
record in whichever specialized store actually owns it (an artifact_id in
SqliteStrategyStore, a run_id in team_runs, a hypothesis id in
HypothesisRegistry, etc.). See
New-talk-agents/new-thinking/new-restructure/phases/phase-0-foundation-plumbing/.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_ledger (
    ledger_id   TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    stage       TEXT NOT NULL,
    event_type  TEXT NOT NULL,
    text        TEXT NOT NULL,
    ref_id      TEXT NOT NULL DEFAULT '',
    source      TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_ticker_ledger_ticker ON ticker_ledger(ticker);
CREATE INDEX IF NOT EXISTS idx_ticker_ledger_stage ON ticker_ledger(stage);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class TickerLedgerEvent:
    ledger_id: str
    ticker: str
    timestamp: str
    stage: str
    event_type: str
    text: str
    ref_id: str = ""
    source: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TickerLedgerEvent":
        return cls(
            ledger_id=row["ledger_id"],
            ticker=row["ticker"],
            timestamp=row["timestamp"],
            stage=row["stage"],
            event_type=row["event_type"],
            text=row["text"],
            ref_id=row.get("ref_id", ""),
            source=row.get("source", ""),
        )


class TickerLedgerStore(SQLiteBackend):
    """Append-only by API shape: no update_event/delete_event method exists
    anywhere on this class. An audit trail that can be edited isn't one --
    the guard here is structural, not a convention."""

    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def add_event(
        self,
        ticker: str,
        stage: str,
        event_type: str,
        text: str,
        *,
        ref_id: str = "",
        source: str = "watchlist",
    ) -> TickerLedgerEvent:
        event = TickerLedgerEvent(
            ledger_id=_new_id(),
            ticker=ticker.upper(),
            timestamp=_now(),
            stage=stage,
            event_type=event_type,
            text=text,
            ref_id=ref_id,
            source=source,
        )
        self.upsert(
            "ticker_ledger",
            {
                "ledger_id": event.ledger_id,
                "ticker": event.ticker,
                "timestamp": event.timestamp,
                "stage": event.stage,
                "event_type": event.event_type,
                "text": event.text,
                "ref_id": event.ref_id,
                "source": event.source,
            },
            conflict_columns=["ledger_id"],
        )
        return event

    def get_events(self, ticker: str) -> list[TickerLedgerEvent]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM ticker_ledger WHERE ticker = ? ORDER BY timestamp ASC",
            (ticker.upper(),),
        ).fetchall()
        return [TickerLedgerEvent.from_row(dict(r)) for r in rows]

    def count_events(
        self,
        ticker: str,
        *,
        stage: str | None = None,
        event_type: str | None = None,
        since: str | None = None,
    ) -> int:
        """Shared-counter discipline: later phases (K-cap checks, repeated-
        rejection pattern detection) must query this store directly rather
        than maintain their own drift-prone counters -- this is the one
        method that makes that possible without each caller hand-rolling
        its own SQL."""
        query = "SELECT COUNT(*) FROM ticker_ledger WHERE ticker = ?"
        params: list[Any] = [ticker.upper()]
        if stage is not None:
            query += " AND stage = ?"
            params.append(stage)
        if event_type is not None:
            query += " AND event_type = ?"
            params.append(event_type)
        if since is not None:
            query += " AND timestamp >= ?"
            params.append(since)
        conn = self._get_conn()
        row = conn.execute(query, params).fetchone()
        return int(row[0]) if row else 0
