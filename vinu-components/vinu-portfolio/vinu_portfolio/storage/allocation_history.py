"""Dated, per-day allocation snapshots -- vinu-portfolio's first piece of
persistent storage of its own. `compute_daily_allocation()` (service.py)
has always computed weights/sleeves/reserve fresh on every call and
returned them, keeping nothing: the only carried state, `self._last_weights`,
is an in-process dict used purely for hysteresis math, gone on restart, and
never queryable as "what was yesterday's allocation." This is the raw
material a future narrating agent (or a Hindsight `retain` pipeline) reads
as the portfolio's own history -- see missing-pieces-of-system/
narating-agents/'s foundation-fixes audit.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS allocation_history (
    allocation_date     TEXT PRIMARY KEY,
    weights             TEXT NOT NULL DEFAULT '[]',
    sleeves             TEXT NOT NULL DEFAULT '{}',
    interval_sleeves    TEXT NOT NULL DEFAULT '{}',
    account_equity      REAL,
    reserve_fraction    REAL NOT NULL DEFAULT 0.0,
    reserve_amount      REAL,
    deployable_equity   REAL,
    created_at          TEXT NOT NULL
);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


@dataclass
class DailyAllocation:
    allocation_date: str
    weights: list[dict[str, Any]] = None  # type: ignore[assignment]
    sleeves: dict[str, float] = None  # type: ignore[assignment]
    interval_sleeves: dict[str, float] = None  # type: ignore[assignment]
    account_equity: float | None = None
    reserve_fraction: float = 0.0
    reserve_amount: float | None = None
    deployable_equity: float | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        if self.weights is None:
            self.weights = []
        if self.sleeves is None:
            self.sleeves = {}
        if self.interval_sleeves is None:
            self.interval_sleeves = {}

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "DailyAllocation":
        def _load(key: str, default: Any) -> Any:
            try:
                return json.loads(row.get(key) or json.dumps(default))
            except Exception:
                return default

        return cls(
            allocation_date=row["allocation_date"],
            weights=_load("weights", []),
            sleeves=_load("sleeves", {}),
            interval_sleeves=_load("interval_sleeves", {}),
            account_equity=row.get("account_equity"),
            reserve_fraction=float(row.get("reserve_fraction") or 0.0),
            reserve_amount=row.get("reserve_amount"),
            deployable_equity=row.get("deployable_equity"),
            created_at=row.get("created_at", ""),
        )


class AllocationHistoryStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record_daily_allocation(
        self,
        *,
        allocation_date: str | None = None,
        weights: list[dict[str, Any]] | None = None,
        sleeves: dict[str, float] | None = None,
        interval_sleeves: dict[str, float] | None = None,
        account_equity: float | None = None,
        reserve_fraction: float = 0.0,
        reserve_amount: float | None = None,
        deployable_equity: float | None = None,
    ) -> DailyAllocation:
        """Idempotent per allocation_date: repeated on-demand calls the same
        day upsert that day's row rather than accumulating duplicates --
        same idempotency shape TickerSnapshotStore.record_daily_snapshot
        already uses, needed here for the same reason: nothing calls
        compute_daily_allocation() on a guaranteed once-daily cadence."""
        date = allocation_date or _today_utc()
        weights = weights or []
        sleeves = sleeves or {}
        interval_sleeves = interval_sleeves or {}
        existing = self.get_allocation(date)
        created_at = existing.created_at if existing else _now()
        self.upsert(
            "allocation_history",
            {
                "allocation_date": date,
                "weights": json.dumps(weights),
                "sleeves": json.dumps(sleeves),
                "interval_sleeves": json.dumps(interval_sleeves),
                "account_equity": account_equity,
                "reserve_fraction": reserve_fraction,
                "reserve_amount": reserve_amount,
                "deployable_equity": deployable_equity,
                "created_at": created_at,
            },
            conflict_columns=["allocation_date"],
        )
        return DailyAllocation(
            allocation_date=date, weights=weights, sleeves=sleeves,
            interval_sleeves=interval_sleeves, account_equity=account_equity,
            reserve_fraction=reserve_fraction, reserve_amount=reserve_amount,
            deployable_equity=deployable_equity, created_at=created_at,
        )

    def get_allocation(self, allocation_date: str) -> Optional[DailyAllocation]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM allocation_history WHERE allocation_date = ?", (allocation_date,)
        ).fetchone()
        return DailyAllocation.from_row(dict(row)) if row else None

    def get_latest_before(self, allocation_date: str) -> Optional[DailyAllocation]:
        """Fail-open lookup for a date with no recorded allocation (weekend,
        holiday, or simply never called that day) -- the most recent row
        strictly before `allocation_date`, or None if there isn't one."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM allocation_history WHERE allocation_date < ? "
            "ORDER BY allocation_date DESC LIMIT 1",
            (allocation_date,),
        ).fetchone()
        return DailyAllocation.from_row(dict(row)) if row else None

    def list_allocations(self) -> list[DailyAllocation]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM allocation_history ORDER BY allocation_date DESC"
        ).fetchall()
        return [DailyAllocation.from_row(dict(r)) for r in rows]
