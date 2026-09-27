"""Cross-process visibility for `PortfolioDrawdownMonitor`'s current
action state. Item #23 findings #2/#3 fix (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): the monitor already
computes a real 4-state `action` (ok/halve/flat/halt) correctly, but
`drawdown_scheduler.py`'s `monitor_main_loop` runs as its own OS process
(same container, split by entrypoint.sh's `&`/`exec`, same shape as
vinu-live's scheduler/poller split -- see that fix's own reasoning) from
the API server process `PortfolioService.compute_daily_allocation()`
runs in. No shared in-memory Python object exists between them, so
`compute_daily_allocation` can't just read `monitor.action` directly.

Same fix shape already used for vinu-live's cross-process kill switch: a
durable, shared-file signal the writer (the monitor loop) updates every
cycle and the reader (`compute_daily_allocation`) polls -- not a second,
independent drawdown tracker, which would risk diverging from the real
one (different peak/start values -> a different, wrong action).

A single-row table (id=1), not an append-only history -- only the
CURRENT action matters for sizing; `allocation_history.py` already owns
dated snapshots of what allocation decisions were actually made.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS drawdown_status (
    id                  INTEGER PRIMARY KEY CHECK (id = 1),
    action              TEXT NOT NULL DEFAULT 'ok',
    current_drawdown    REAL NOT NULL DEFAULT 0.0,
    threshold_breached  INTEGER NOT NULL DEFAULT 0,
    updated_at          TEXT NOT NULL
);
"""

SCHEMA_VERSION = 1
MIGRATIONS: list[tuple[str, str]] = []


@dataclass
class DrawdownStatus:
    action: str = "ok"
    current_drawdown: float = 0.0
    threshold_breached: bool = False
    updated_at: str = ""


class DrawdownStatusStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION
    MIGRATIONS = MIGRATIONS

    def record(self, action: str, current_drawdown: float, threshold_breached: bool) -> None:
        self.upsert(
            "drawdown_status",
            {
                "id": 1,
                "action": action,
                "current_drawdown": current_drawdown,
                "threshold_breached": int(threshold_breached),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            conflict_columns=["id"],
        )

    def get(self) -> DrawdownStatus:
        """Never seen a row yet (fresh deployment, or the monitor worker
        hasn't completed its first cycle) -> "ok"/no tilt, same fail-open
        posture as every other tilt-data fetch in this pipeline -- an
        absent signal must never be treated as an active halt/flat."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM drawdown_status WHERE id = 1").fetchone()
        if row is None:
            return DrawdownStatus()
        return DrawdownStatus(
            action=row["action"],
            current_drawdown=row["current_drawdown"],
            threshold_breached=bool(row["threshold_breached"]),
            updated_at=row["updated_at"],
        )
