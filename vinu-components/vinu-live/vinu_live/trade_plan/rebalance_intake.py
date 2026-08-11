"""Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
phase-5-monitor-extend/): the rebalance-request intake point Phase 2's
capital_allocator rebalancer can call -- confirmed nowhere existed before
this phase, per 01-plan.md item 4. Deliberately a queue, not a direct
action: TradePlanOrchestrator's own per-cycle evaluation folds a pending
request in as ONE MORE advisory input alongside its real
invalidation/contingency rules, and can decline it. This is what actually
enforces "the rebalancer can only request, never act directly" at the
code level (02-guard-rail.md), not just in prose.

SQLite-backed, not in-memory: the HTTP intake route (server/app.py)
constructs a fresh TradePlanOrchestrator per request -- a completely
different Python object than the long-running trade-plan-worker's own
orchestrator instance that actually evaluates pending requests each
cycle. An in-memory dict would make every HTTP-submitted request silently
invisible to the real cycle -- exactly the "no decision on shared
persistence yet" gap Phase 5's own record flagged as the reason the HTTP
route wasn't built yet. Both orchestrator instances point at the same
on-disk `rebalance_requests.db` under `config.data_root`, same pattern as
`trade_plan_book.db`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS rebalance_requests (
    symbol       TEXT PRIMARY KEY,
    reason       TEXT NOT NULL,
    requested_at REAL NOT NULL
);
"""


@dataclass
class RebalanceRequest:
    symbol: str
    reason: str
    requested_at: float


class RebalanceRequestQueue(SQLiteBackend):
    """One-pending-request-per-symbol (a newer request for the same symbol
    replaces an older unconsumed one, via upsert) -- there is no reason to
    act on a stale reallocation reason once a fresher one exists for the
    same symbol."""

    SCHEMA = SCHEMA
    SCHEMA_VERSION = 1

    def submit(self, symbol: str, reason: str) -> RebalanceRequest:
        request = RebalanceRequest(symbol=symbol.upper(), reason=reason, requested_at=time.time())
        self.upsert(
            "rebalance_requests",
            {"symbol": request.symbol, "reason": request.reason, "requested_at": request.requested_at},
            conflict_columns=["symbol"],
        )
        return request

    def pending_for(self, symbol: str) -> RebalanceRequest | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM rebalance_requests WHERE symbol = ?", (symbol.upper(),),
        ).fetchone()
        if row is None:
            return None
        return RebalanceRequest(symbol=row["symbol"], reason=row["reason"], requested_at=row["requested_at"])

    def consume(self, symbol: str) -> None:
        """Removes a pending request once the orchestrator has evaluated
        it (whether honored or declined) -- a request is considered once,
        not re-evaluated identically every cycle forever."""
        conn = self._get_conn()
        conn.execute("DELETE FROM rebalance_requests WHERE symbol = ?", (symbol.upper(),))
        conn.commit()
