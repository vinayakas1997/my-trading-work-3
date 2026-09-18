"""Durable, one-row-per-calendar-day home for market_regime_analogue.py's
get_market_regime_stats_for_today() output.

That function already computes a real, system-wide market-regime signal
once per day (positive_ratio/avg_return/median_return/max_drawdown across
the current window's KNN-matched historical analogues) -- see its own
`_DAY_CACHE`. But the cache is in-memory, process-lifetime, and cleared
every day it advances, so nothing durable ever remembers what "today's"
regime read looked like on any past day. That's the real gap analysis J
(missing-pieces-of-system/.../06-external-signal-cross-check.md) needs
closed: a history to detect drift in, not a new regime-classification
scheme (there already is one; it just wasn't being kept).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS market_regime_history (
    date            TEXT PRIMARY KEY,
    positive_ratio  REAL NOT NULL,
    avg_return      REAL NOT NULL,
    median_return   REAL NOT NULL,
    max_drawdown    REAL NOT NULL,
    n_matches       INTEGER NOT NULL,
    n_positive      INTEGER NOT NULL,
    n_negative      INTEGER NOT NULL,
    recorded_at     TEXT NOT NULL
);
"""


class MarketRegimeHistoryStore(SQLiteBackend):
    """`date` (the same cache_key get_market_regime_stats_for_today already
    computes -- today's UTC date) is the primary key: at most one row per
    day, written the first time that day's stats are computed. Later calls
    the same day hit the day-cache before ever reaching record(), so this
    never needs an explicit "already recorded today" check of its own."""

    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def record(self, date: str, stats: dict[str, Any]) -> None:
        if not stats or stats.get("n_matches", 0) <= 0:
            return
        self.insert_or_ignore(
            "market_regime_history",
            {
                "date": date,
                "positive_ratio": float(stats.get("positive_ratio", 0.0)),
                "avg_return": float(stats.get("avg_return", 0.0)),
                "median_return": float(stats.get("median_return", 0.0)),
                "max_drawdown": float(stats.get("max_drawdown", 0.0)),
                "n_matches": int(stats.get("n_matches", 0)),
                "n_positive": int(stats.get("n_positive", 0)),
                "n_negative": int(stats.get("n_negative", 0)),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
            conflict_columns=["date"],
        )

    def all_history(self) -> list[dict[str, Any]]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM market_regime_history ORDER BY date ASC"
        ).fetchall()
        return [dict(row) for row in rows]
