"""Real, persistent daily order-count/volume tracking for OrderGuard's
mandate.max_daily_orders / max_daily_trade_volume checks.

Found while evaluating OrderGuard's other gates for their own check-then-
act races (the kill-switch race fix's own follow-up note: "OrderGuard's
other gates -- mandate limits, market hours, active-artifact check,
portfolio concentration -- were not evaluated for their own check-then-
act windows"). What was actually found here is worse than a race window:
`OrderGuard` is constructed fresh on every `trade_tool.py` `execute()`
call (confirmed by reading trade_tool.py directly -- `guard =
OrderGuard(...)` inside `execute()`, never a shared long-lived instance),
and the daily counters were plain in-process dict attributes on
`OrderGuard` itself. Every single call started from an empty dict, so
`max_daily_orders`/`max_daily_trade_volume` could never actually trigger
a rejection, no matter how many real orders had already gone through
today -- not a narrow race window, a completely non-functioning check.

Fixed the same way every other cross-call counter in this codebase is
fixed: a real, persistent, shared SQLite-backed store
(`vinu_infra.sqlite.SQLiteBackend`), not a bigger in-memory structure
that would just move the same bug (state lost between calls/processes)
somewhere else. No cross-process locking here, unlike kill_switch.py's
kill_switch_lock() -- this is a soft rate limit, not a safety-critical
gate, and the worst case of an unlocked read-then-write race (two orders
for the same symbol in the same instant both undercounting by one) is an
occasionally-too-permissive daily cap, not money moving while halted.
"""

from __future__ import annotations

import os
import random
import sqlite3
import time
from datetime import date
from pathlib import Path

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_limits (
    symbol      TEXT NOT NULL,
    date        TEXT NOT NULL,
    order_count INTEGER NOT NULL DEFAULT 0,
    volume      REAL NOT NULL DEFAULT 0.0,
    PRIMARY KEY (symbol, date)
);
"""

# Same dev-fallback shape as kill_switch.py's AuditLogger.LOG_PATH --
# VINU_AGENT_DATA_ROOT=/data in the real Docker stack (the only writable
# mount), Path.home()/".vinu" for a bare Windows/local dev run.
DEFAULT_DAILY_LIMIT_DB_PATH = Path(
    os.environ.get(
        "VINU_AGENT_DAILY_LIMIT_DB",
        os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu")) + "/daily_limits.db",
    )
)


def _today() -> str:
    return date.today().isoformat()


class DailyLimitStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def count_today(self, symbol: str) -> int:
        row = self._row_for(symbol)
        return int(row[0]) if row else 0

    def count_today_total(self) -> int:
        """Stage 2 (how-to-make-it-live.md #8): sum of order_count across
        EVERY symbol today, for OrderGuard's portfolio-wide daily order cap
        -- max_daily_orders above is per-symbol and 10/symbol x N traded
        symbols has no ceiling on its own."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COALESCE(SUM(order_count), 0) FROM daily_limits WHERE date = ?",
            (_today(),),
        ).fetchone()
        return int(row[0]) if row else 0

    def volume_today(self, symbol: str) -> float:
        row = self._row_for(symbol)
        return float(row[1]) if row else 0.0

    def record_order(self, symbol: str, value: float) -> None:
        """Called from OrderGuard.pre_approve() -- once per order that
        actually clears the guard, immediately before submission, same
        point the old in-memory counter was incremented.

        situation-test/01-daily-order-limit-race.md found this was a real
        SELECT-then-INSERT/UPDATE TOCTOU race: 30 threads hammering the same
        (symbol, date) row mostly crashed with unhandled
        sqlite3.OperationalError ("database is locked") or
        sqlite3.IntegrityError ("UNIQUE constraint failed") instead of the
        module docstring's claimed worst case of "an occasionally-too-
        permissive daily cap". The IntegrityError is gone for good with the
        single atomic upsert below (no read-then-decide branch left for
        another thread's commit to land inside of). The OperationalError
        turned out to survive that fix, and even a busy_timeout pragma
        ordering fix in vinu_infra.sqlite.SQLiteBackend -- empirically, on
        Windows, a burst of ~30 threads each opening/closing their own
        connection against one file (the real production shape: fresh
        DailyLimitStore per trade_tool.py execute() call) can still return
        "database is locked" in under 3ms, far faster than the 5s
        busy_timeout, meaning the OS-level lock contention isn't always
        routed through SQLite's own retry loop. A small in-process retry
        with backoff -- the standard fix for exactly this SQLite pattern --
        closes the gap; re-verified against the same 30-thread harness
        across many repeated runs with zero failures.
        """
        today = _today()
        last_error: sqlite3.OperationalError | None = None
        for attempt in range(5):
            try:
                conn = self._get_conn()
                conn.execute(
                    """
                    INSERT INTO daily_limits (symbol, date, order_count, volume)
                    VALUES (?, ?, 1, ?)
                    ON CONFLICT (symbol, date) DO UPDATE SET
                        order_count = order_count + 1,
                        volume = volume + excluded.volume
                    """,
                    (symbol, today, value),
                )
                conn.commit()
                return
            except sqlite3.OperationalError as e:
                if "locked" not in str(e).lower() and "busy" not in str(e).lower():
                    raise
                last_error = e
                time.sleep(0.02 * (2**attempt) + random.uniform(0, 0.02))
        raise last_error  # type: ignore[misc]

    def _row_for(self, symbol: str):
        conn = self._get_conn()
        return conn.execute(
            "SELECT order_count, volume FROM daily_limits WHERE symbol = ? AND date = ?",
            (symbol, _today()),
        ).fetchone()
