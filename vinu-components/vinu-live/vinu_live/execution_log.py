"""Append-only ledger of what the hourly scheduler tried to execute, and what came back.

Why this exists (the-inconsistencies-v2, Phase 5 -- the groundwork for a real execution-parity check):
the scheduler path writes nothing to the trade-plan book, so after an hour there was no durable record of
"I tried to buy 40 AAPL at a reference price of 187.20, spread 3.1 bps, as a market order, and the broker
said X" -- only log lines. Comparing a backtest's assumed fills with reality needs exactly that: the price
the order was sized at, the spread at decision time, the order type, and the outcome.

Deliberately NOT the trade-plan book: the orchestrator reconciles that book against the broker and counts its
positions in its own breaker and cooldown, so scheduler rows there would look like drift to it. This is a
separate database file (`execution_log.db`) nothing else reads.

Best-effort by construction: `record` never raises, so a ledger problem can never stop an order. It records
the broker's *submission* answer (status, order id, broker status). It does not yet know the fill price -- an
order is usually still working when the answer comes back; enriching rows with the fill is a separate step
(it needs an order-lookup route on the agent API).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

LOG = logging.getLogger(__name__)


class ExecutionLog(SQLiteBackend):
    SCHEMA = """
        CREATE TABLE IF NOT EXISTS scheduler_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT NOT NULL,
            cycle_id TEXT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            slice_number INTEGER,
            total_slices INTEGER,
            order_type TEXT,
            reduce_only INTEGER NOT NULL DEFAULT 0,
            reference_price REAL,
            spread_bps REAL,
            limit_price REAL,
            client_order_id TEXT,
            outcome TEXT NOT NULL,
            http_status INTEGER,
            order_id TEXT,
            broker_status TEXT,
            reason TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_sched_exec_symbol ON scheduler_executions(symbol, id);
    """
    SCHEMA_VERSION = 2
    # v2: fill enrichment (the quote mid at decision time, and what the broker later reported).
    MIGRATIONS = [
        ("ALTER TABLE scheduler_executions ADD COLUMN quote_mid REAL", "decision-time quote mid"),
        ("ALTER TABLE scheduler_executions ADD COLUMN fill_price REAL", "broker average fill price"),
        ("ALTER TABLE scheduler_executions ADD COLUMN filled_qty REAL", "broker filled quantity"),
        ("ALTER TABLE scheduler_executions ADD COLUMN fill_status TEXT", "broker order status when last checked"),
        ("ALTER TABLE scheduler_executions ADD COLUMN fill_checked_at TEXT", "when the fill was last looked up"),
        ("ALTER TABLE scheduler_executions ADD COLUMN slippage_bps REAL", "cost vs reference in bps (positive = worse)"),
        ("ALTER TABLE scheduler_executions ADD COLUMN slippage_ref TEXT", "what slippage was measured against: mid | close"),
    ]

    def record(self, **row: Any) -> None:
        """Insert one row. Unknown keys are ignored; any error is logged at debug and swallowed."""
        try:
            cols = {
                "cycle_id", "symbol", "side", "qty", "slice_number", "total_slices", "order_type", "reduce_only",
                "reference_price", "spread_bps", "limit_price", "client_order_id", "outcome", "http_status",
                "order_id", "broker_status", "reason", "quote_mid",
            }
            data = {k: v for k, v in row.items() if k in cols}
            data["reduce_only"] = int(bool(data.get("reduce_only")))
            data["recorded_at"] = datetime.now(timezone.utc).isoformat()
            names = ", ".join(data)
            marks = ", ".join("?" for _ in data)
            conn = self._get_conn()
            conn.execute(f"INSERT INTO scheduler_executions ({names}) VALUES ({marks})", list(data.values()))
            conn.commit()
        except Exception as e:  # noqa: BLE001 -- a ledger problem must never stop an order
            LOG.debug("execution ledger write failed: %s", e)

    def recent(self, limit: int = 100, symbol: str | None = None) -> list[dict[str, Any]]:
        conn = self._get_conn()
        if symbol:
            rows = conn.execute(
                "SELECT * FROM scheduler_executions WHERE symbol = ? ORDER BY id DESC LIMIT ?", (symbol.upper(), int(limit)),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM scheduler_executions ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()
        return [dict(r) for r in rows]

    def bought_symbols(self) -> set[str]:
        """Upper-case symbols the scheduler has ever had a BUY accepted for (outcome `submitted`). This is what
        'the scheduler opened it' means for the ownership rule that lets it close a position nothing targets any
        more. Limits: accepted is not filled, and 'ever bought' is not 'still holds only what it bought'."""
        conn = self._get_conn()
        return {
            str(r["symbol"]).upper() for r in conn.execute(
                "SELECT DISTINCT symbol FROM scheduler_executions WHERE side = 'buy' AND outcome = 'submitted'",
            ).fetchall()
        }

    FINAL_FILL_STATUSES = frozenset({"filled", "canceled", "cancelled", "expired", "rejected", "done_for_day"})

    def unresolved_orders(self, limit: int = 25, max_age_days: float = 7.0) -> list[dict[str, Any]]:
        """Accepted orders (with a broker order id) whose fill has not reached a final status yet, oldest first,
        younger than `max_age_days`. These are the rows the enrichment pass asks the broker about."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        conn = self._get_conn()
        marks = ",".join("?" for _ in self.FINAL_FILL_STATUSES)
        rows = conn.execute(
            f"SELECT * FROM scheduler_executions WHERE outcome = 'submitted' AND order_id IS NOT NULL AND order_id != '' "
            f"AND recorded_at >= ? AND (fill_status IS NULL OR fill_status NOT IN ({marks})) ORDER BY id ASC LIMIT ?",
            [cutoff, *sorted(self.FINAL_FILL_STATUSES), int(limit)],
        ).fetchall()
        return [dict(r) for r in rows]

    def record_fill(
        self, row_id: int, *, fill_status: str | None, fill_price: float | None, filled_qty: float | None,
    ) -> float | None:
        """Write what the broker reported and return the slippage in bps (None when it cannot be computed).
        Slippage is positive when the fill was WORSE than the reference: a buy above it, a sell below it. The
        reference is the decision-time quote mid when one was recorded, else the sizing reference price (the last
        daily close, which also contains any overnight gap -- so it overstates execution cost; the column
        `slippage_ref` says which one was used). Never raises."""
        try:
            conn = self._get_conn()
            row = conn.execute("SELECT side, reference_price, quote_mid FROM scheduler_executions WHERE id = ?", (row_id,)).fetchone()
            slip, ref_kind = None, None
            if row is not None and fill_price and fill_price > 0:
                ref, ref_kind = (row["quote_mid"], "mid") if row["quote_mid"] else (row["reference_price"], "close")
                if ref and ref > 0:
                    signed = (fill_price - ref) if row["side"] == "buy" else (ref - fill_price)
                    slip = signed / ref * 10_000.0
                else:
                    ref_kind = None
            conn.execute(
                "UPDATE scheduler_executions SET fill_status = ?, fill_price = ?, filled_qty = ?, fill_checked_at = ?, "
                "slippage_bps = ?, slippage_ref = ? WHERE id = ?",
                (fill_status, fill_price, filled_qty, datetime.now(timezone.utc).isoformat(), slip, ref_kind, row_id),
            )
            conn.commit()
            return slip
        except Exception as e:  # noqa: BLE001
            LOG.debug("execution ledger fill write failed: %s", e)
            return None

    def summary(self) -> dict[str, Any]:
        """Counts by outcome, plus the reference-price and spread coverage a later parity check will depend on."""
        conn = self._get_conn()
        by_outcome = {r["outcome"]: r["n"] for r in conn.execute(
            "SELECT outcome, COUNT(*) AS n FROM scheduler_executions GROUP BY outcome").fetchall()}
        cov = conn.execute(
            "SELECT COUNT(*) AS n, SUM(reference_price IS NOT NULL) AS with_price, SUM(spread_bps IS NOT NULL) AS with_spread "
            "FROM scheduler_executions").fetchone()
        fills = conn.execute(
            "SELECT COUNT(*) AS n, AVG(slippage_bps) AS mean_slip FROM scheduler_executions WHERE fill_price IS NOT NULL").fetchone()
        slips = sorted(r[0] for r in conn.execute(
            "SELECT slippage_bps FROM scheduler_executions WHERE slippage_bps IS NOT NULL").fetchall())
        median = (slips[len(slips) // 2] if len(slips) % 2 else (slips[len(slips) // 2 - 1] + slips[len(slips) // 2]) / 2) if slips else None
        return {
            "total": cov["n"], "by_outcome": by_outcome,
            "with_reference_price": cov["with_price"] or 0, "with_spread": cov["with_spread"] or 0,
            "filled": fills["n"] or 0, "with_slippage": len(slips),
            "mean_slippage_bps": fills["mean_slip"], "median_slippage_bps": median,
        }
