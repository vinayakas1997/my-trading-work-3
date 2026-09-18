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
    requested_at REAL NOT NULL,
    critical     INTEGER NOT NULL DEFAULT 0
);

-- Append-only history of every consumed request -- `rebalance_requests`
-- above is a one-row-per-symbol working queue (consume() deletes the row),
-- so it can never answer "how did past critical bypasses turn out"
-- (25-A-Y-details/03-execution-money-flow.md, analysis U). This table is
-- the new writer that closes that gap: one row per consume(), never
-- updated or deleted.
CREATE TABLE IF NOT EXISTS rebalance_request_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol       TEXT NOT NULL,
    reason       TEXT NOT NULL,
    requested_at REAL NOT NULL,
    critical     INTEGER NOT NULL DEFAULT 0,
    consumed_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rebalance_history_symbol ON rebalance_request_history(symbol);
"""


@dataclass
class RebalanceRequest:
    symbol: str
    reason: str
    requested_at: float
    # how-to-make-it-live.md #23: a critical request bypasses the
    # orchestrator's 5% unrealized-gain protect -- for a genuinely urgent
    # reallocation the allocator should be able to force through, not have
    # declined indefinitely because the position happens to be up.
    critical: bool = False


class RebalanceRequestQueue(SQLiteBackend):
    """One-pending-request-per-symbol (a newer request for the same symbol
    replaces an older unconsumed one, via upsert) -- there is no reason to
    act on a stale reallocation reason once a fresher one exists for the
    same symbol."""

    SCHEMA = SCHEMA
    SCHEMA_VERSION = 2
    MIGRATIONS = [
        ("ALTER TABLE rebalance_requests ADD COLUMN critical INTEGER NOT NULL DEFAULT 0",
         "add critical flag to rebalance_requests (how-to-make-it-live.md #23)"),
    ]

    def submit(self, symbol: str, reason: str, critical: bool = False) -> RebalanceRequest:
        request = RebalanceRequest(
            symbol=symbol.upper(), reason=reason, requested_at=time.time(), critical=bool(critical),
        )
        self.upsert(
            "rebalance_requests",
            {
                "symbol": request.symbol, "reason": request.reason,
                "requested_at": request.requested_at, "critical": int(request.critical),
            },
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
        critical = bool(row["critical"]) if "critical" in row.keys() else False
        return RebalanceRequest(
            symbol=row["symbol"], reason=row["reason"],
            requested_at=row["requested_at"], critical=critical,
        )

    def consume(self, symbol: str) -> None:
        """Removes a pending request once the orchestrator has evaluated
        it (whether honored or declined) -- a request is considered once,
        not re-evaluated identically every cycle forever. Archives the row
        into `rebalance_request_history` first so a later analysis can
        still look up "was this symbol's request critical" even though the
        working queue itself no longer holds it."""
        conn = self._get_conn()
        symbol = symbol.upper()
        row = conn.execute(
            "SELECT reason, requested_at, critical FROM rebalance_requests WHERE symbol = ?", (symbol,),
        ).fetchone()
        if row is not None:
            conn.execute(
                "INSERT INTO rebalance_request_history "
                "(symbol, reason, requested_at, critical, consumed_at) VALUES (?,?,?,?,?)",
                (symbol, row["reason"], row["requested_at"], row["critical"], time.time()),
            )
        conn.execute("DELETE FROM rebalance_requests WHERE symbol = ?", (symbol,))
        conn.commit()

    def history_for(self, symbol: str, limit: int = 200) -> list[RebalanceRequest]:
        """All past consumed requests for a symbol, most recent first --
        the read side of the history writer above."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT symbol, reason, requested_at, critical FROM rebalance_request_history "
            "WHERE symbol = ? ORDER BY consumed_at DESC LIMIT ?",
            (symbol.upper(), limit),
        ).fetchall()
        return [
            RebalanceRequest(
                symbol=r["symbol"], reason=r["reason"],
                requested_at=r["requested_at"], critical=bool(r["critical"]),
            )
            for r in rows
        ]

    def all_history(self, limit: int = 5000) -> list[RebalanceRequest]:
        """Every consumed request across all symbols, most recent first --
        what analysis U actually needs (per-symbol AND system rollup)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT symbol, reason, requested_at, critical FROM rebalance_request_history "
            "ORDER BY consumed_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            RebalanceRequest(
                symbol=r["symbol"], reason=r["reason"],
                requested_at=r["requested_at"], critical=bool(r["critical"]),
            )
            for r in rows
        ]
