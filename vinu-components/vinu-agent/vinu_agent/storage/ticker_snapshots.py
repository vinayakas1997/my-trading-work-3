"""Dated, per-day per-ticker snapshots -- distinct from `TickerSummaryStore`
(one row per ticker, overwritten to latest on every refresh) and
`TickerLedgerStore` (an append-only event log with no "state as of date X"
query). Nothing in this codebase kept a queryable "what was true about this
ticker on a specific past day" until this store existed -- see the
foundation-fixes audit in missing-pieces-of-system/narating-agents/. This is
the raw material a future narrating agent (or a Hindsight `retain` pipeline)
reads as "yesterday."
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS ticker_daily_snapshots (
    ticker              TEXT NOT NULL,
    snapshot_date       TEXT NOT NULL,
    summary             TEXT NOT NULL DEFAULT '',
    angle_digest        TEXT NOT NULL DEFAULT '{}',
    angles_with_data    INTEGER NOT NULL DEFAULT 0,
    angle_count         INTEGER NOT NULL DEFAULT 0,
    source_run_id       TEXT NOT NULL DEFAULT '',
    created_at          TEXT NOT NULL,
    PRIMARY KEY (ticker, snapshot_date)
);
CREATE INDEX IF NOT EXISTS idx_ticker_daily_snapshots_date ON ticker_daily_snapshots(snapshot_date);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class TickerDailySnapshot:
    ticker: str
    snapshot_date: str
    summary: str = ""
    angle_digest: dict[str, Any] = None  # type: ignore[assignment]
    angles_with_data: int = 0
    angle_count: int = 0
    source_run_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.angle_digest is None:
            self.angle_digest = {}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "TickerDailySnapshot":
        try:
            angle_digest = json.loads(row.get("angle_digest") or "{}")
            if not isinstance(angle_digest, dict):
                angle_digest = {}
        except Exception:
            angle_digest = {}
        return cls(
            ticker=row["ticker"],
            snapshot_date=row["snapshot_date"],
            summary=row.get("summary", ""),
            angle_digest=angle_digest,
            angles_with_data=int(row.get("angles_with_data") or 0),
            angle_count=int(row.get("angle_count") or 0),
            source_run_id=row.get("source_run_id", ""),
            created_at=row.get("created_at", ""),
        )


class TickerSnapshotStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record_daily_snapshot(
        self,
        ticker: str,
        *,
        snapshot_date: str | None = None,
        summary: str = "",
        angle_digest: dict[str, Any] | None = None,
        angles_with_data: int = 0,
        angle_count: int = 0,
        source_run_id: str = "",
    ) -> TickerDailySnapshot:
        """Idempotent per (ticker, snapshot_date): a same-day re-refresh
        upserts that day's row rather than accumulating duplicates -- same
        idempotency shape AppendDailyReturnRequest's trade_date field
        already uses elsewhere in this codebase."""
        ticker = ticker.upper()
        date = snapshot_date or _today_utc()
        angle_digest = angle_digest or {}
        existing = self.get_snapshot(ticker, date)
        created_at = existing.created_at if existing else _now()
        self.upsert(
            "ticker_daily_snapshots",
            {
                "ticker": ticker,
                "snapshot_date": date,
                "summary": summary,
                "angle_digest": json.dumps(angle_digest),
                "angles_with_data": angles_with_data,
                "angle_count": angle_count,
                "source_run_id": source_run_id,
                "created_at": created_at,
            },
            conflict_columns=["ticker", "snapshot_date"],
        )
        return TickerDailySnapshot(
            ticker=ticker, snapshot_date=date, summary=summary, angle_digest=angle_digest,
            angles_with_data=angles_with_data, angle_count=angle_count,
            source_run_id=source_run_id, created_at=created_at,
        )

    def get_snapshot(self, ticker: str, snapshot_date: str) -> Optional[TickerDailySnapshot]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ticker_daily_snapshots WHERE ticker = ? AND snapshot_date = ?",
            (ticker.upper(), snapshot_date),
        ).fetchone()
        return TickerDailySnapshot.from_row(dict(row)) if row else None

    def get_latest_before(self, ticker: str, snapshot_date: str) -> Optional[TickerDailySnapshot]:
        """Fail-open lookup for a date that fell on a weekend/holiday gap
        (or any day the ticker simply wasn't refreshed) -- the most recent
        snapshot strictly before `snapshot_date`, or None if there isn't
        one."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM ticker_daily_snapshots WHERE ticker = ? AND snapshot_date < ? "
            "ORDER BY snapshot_date DESC LIMIT 1",
            (ticker.upper(), snapshot_date),
        ).fetchone()
        return TickerDailySnapshot.from_row(dict(row)) if row else None

    def list_snapshots(self, ticker: str) -> list[TickerDailySnapshot]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM ticker_daily_snapshots WHERE ticker = ? ORDER BY snapshot_date DESC",
            (ticker.upper(),),
        ).fetchall()
        return [TickerDailySnapshot.from_row(dict(r)) for r in rows]
