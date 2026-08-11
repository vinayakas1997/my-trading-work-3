"""Debrief-on-close — the missing read-back half of item 3's decision
journal. `trade_plan_tool.py`'s `_schedule_journal_write` records a thesis
into vinu-research's HypothesisRegistry when a plan is generated, but
nothing wrote the outcome back when the position actually closed, so a
thesis just sat unresolved forever. See
`04-agentic-still-refinement/implementation-plan-from-04/vinu-agent/plan.md`
Piece 2 for why this matters.

Detection has two tiers, not one:

1. **Primary — replay recent filled orders.** Whichever caller already
   calls `broker.get_positions()` once per turn (mirroring
   `GroundTruthInjector`) also calls `check_and_debrief()`, which now also
   pulls `broker.get_orders(status="closed", limit=...)` and replays filled
   buy/sell fills (oldest first) on top of the last known per-symbol
   position. Every point a symbol's replayed quantity crosses from held to
   flat is a close, keyed by that sell order's own broker-assigned
   `order_id` — a real unique identity Alpaca already gives every fill, not
   invented here. This is what makes a position that both opens *and*
   fully closes inside a single polling gap visible at all: there is no
   `get_positions()` snapshot of the intermediate held state to diff
   against, but the fills that produced it are still in the order history.
2. **Fallback — snapshot diff.** Anything the fetched order window missed
   (lookback too small, a very old position, the order API briefly down)
   falls back to the original before/after diff of `get_positions()`
   against the last saved snapshot, exactly as before this tier was added.

Both tiers persist state *before* writing any evidence, not after — a
crash mid-loop can drop at most one debrief (a swallowed miss, matching
this class's own documented best-effort contract below) instead of
reprocessing and double-writing whatever had already succeeded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_THESIS_STATUSES = {"testing", "exploring", "monitoring"}

# Ring-buffer cap on how many processed order_ids the state file remembers.
# Only needs to comfortably outlive one lookback window's worth of fills --
# an order_id older than that can never be re-fetched by
# DEBRIEF_ORDER_LOOKBACK anyway, so remembering it forever is pure growth
# with no dedup benefit.
_MAX_PROCESSED_ORDER_IDS = 2000


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"positions": {}, "processed_order_ids": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"positions": {}, "processed_order_ids": []}
    if "positions" not in raw:
        # Pre-existing state file from before fill-based detection: the
        # whole dict *was* the positions map (symbol -> {qty, avg_entry_price}).
        return {"positions": raw, "processed_order_ids": []}
    return {
        "positions": dict(raw.get("positions", {})),
        "processed_order_ids": list(raw.get("processed_order_ids", [])),
    }


def _save_state(path: Path, positions: dict[str, dict], processed_order_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({
            "positions": positions,
            "processed_order_ids": processed_order_ids[-_MAX_PROCESSED_ORDER_IDS:],
        }),
        encoding="utf-8",
    )


class PositionCloseDetector:
    """Best-effort: any failure here is logged and swallowed, never raised —
    this is an audit/learning aid, not part of the trade path."""

    def __init__(
        self,
        registry: Any,
        state_path: str | Path,
        services_config: dict | None = None,
        ticker_ledger_store: Any = None,
    ) -> None:
        self._registry = registry
        self._state_path = Path(state_path)
        # No longer read for vinu_research (that's now an in-process call,
        # see .research_link) -- kept for interface stability in case a
        # future evidence source needs a service URL.
        self._services_config = services_config or {}
        # Optional: when set, a "contradicts" close also gets a TickerLedger
        # row (stage="debrief", event_type="thesis_contradicted") so
        # significance_triage.py's detect_thesis_contradiction_pattern can
        # see it the same way every other pattern detector reads TickerLedger
        # -- never a second, separately-drifting counter.
        self._ticker_ledger_store = ticker_ledger_store

    def check_and_debrief(self, broker: Any, session_id: str = "") -> list[dict]:
        try:
            current = {
                p.symbol: {"qty": float(p.qty), "avg_entry_price": float(p.avg_entry_price)}
                for p in broker.get_positions()
                if float(p.qty) > 0
            }
        except Exception:
            logger.debug("PositionCloseDetector: get_positions failed", exc_info=True)
            return []

        state = _load_state(self._state_path)
        positions = state["positions"]
        processed = set(state["processed_order_ids"])

        fills = self._fetch_recent_fills(broker)
        closes, replayed_positions = self._replay_fills(positions, fills, processed)

        # Fallback tier: any symbol the replay still shows as held, but the
        # broker now reports flat, with no fill in this poll's lookback
        # window accounting for it -- the order that closed it fell outside
        # DEBRIEF_ORDER_LOOKBACK. Reuse the original snapshot-diff exit-price
        # lookup for these, same as before this tier existed.
        fill_closed_symbols = {c["symbol"] for c in closes}
        fallback_closed_symbols = [
            sym for sym, pos in replayed_positions.items()
            if sym not in current and sym not in fill_closed_symbols and pos["qty"] > 1e-9
        ]

        # Broker's own current holdings are always ground truth -- they
        # reflect fills outside the lookback window, manual/UI trades,
        # corporate actions, anything the replay above can't see. Winning
        # over the replay's guess for every symbol it currently reports.
        final_positions = {
            sym: pos for sym, pos in replayed_positions.items()
            if sym not in current and sym not in fallback_closed_symbols
        }
        final_positions.update(current)

        new_processed = sorted(processed | {c["order_id"] for c in closes})

        # Persist before writing any evidence -- see module docstring.
        _save_state(self._state_path, final_positions, new_processed)

        results: list[dict] = []
        for close in closes:
            outcome = self._debrief_close(
                close["symbol"], close["entry_price"], close["exit_price"], close["qty"],
                session_id,
            )
            if outcome is not None:
                results.append(outcome)
        for sym in fallback_closed_symbols:
            outcome = self._debrief_snapshot_fallback(sym, replayed_positions[sym], session_id)
            if outcome is not None:
                results.append(outcome)

        return results

    def _fetch_recent_fills(self, broker: Any) -> list[Any]:
        try:
            from .alpaca import DEBRIEF_ORDER_LOOKBACK

            orders = broker.get_orders(status="closed", limit=DEBRIEF_ORDER_LOOKBACK)
        except Exception:
            logger.debug("PositionCloseDetector: get_orders failed", exc_info=True)
            return []
        return [o for o in (orders or []) if getattr(o, "status", "") == "filled"]

    def _replay_fills(
        self, positions: dict[str, dict], fills: list[Any], processed: set[str],
    ) -> tuple[list[dict], dict[str, dict]]:
        """Replays not-yet-processed filled orders, oldest first, on top of
        the last known per-symbol (qty, avg_entry_price). Every sell fill
        that brings a symbol's replayed qty to (approximately) zero is a
        close, carrying that fill's own order_id as its dedup identity."""
        replayed = {sym: dict(pos) for sym, pos in positions.items()}
        closes: list[dict] = []

        new_fills = [f for f in fills if f.order_id and f.order_id not in processed]
        new_fills.sort(key=lambda o: o.updated_at or o.created_at or "")

        for order in new_fills:
            symbol = (order.symbol or "").upper()
            if not symbol:
                continue
            qty = float(order.filled_qty or 0.0)
            price = order.filled_avg_price
            if order.side == "sell" and price is None:
                # Some fills don't carry a fill price (older API responses,
                # replay brokers that omit it) -- fall back to a current
                # price lookup rather than dropping the close undetected.
                price = self._fetch_exit_price(symbol)
            if qty <= 0 or price is None:
                continue

            pos = replayed.setdefault(symbol, {"qty": 0.0, "avg_entry_price": 0.0})
            if order.side == "buy":
                new_qty = pos["qty"] + qty
                if new_qty > 0:
                    pos["avg_entry_price"] = (
                        pos["avg_entry_price"] * pos["qty"] + price * qty
                    ) / new_qty
                pos["qty"] = new_qty
            elif order.side == "sell":
                entry_price = pos["avg_entry_price"]
                pos["qty"] = max(0.0, pos["qty"] - qty)
                if pos["qty"] <= 1e-9:
                    pos["qty"] = 0.0
                    pos["avg_entry_price"] = 0.0
                    if entry_price > 0:
                        closes.append({
                            "order_id": order.order_id,
                            "symbol": symbol,
                            "entry_price": entry_price,
                            "exit_price": price,
                            "qty": qty,
                        })
                    # else: sold something we never saw a tracked entry for
                    #  (e.g. a pre-existing holding from before this
                    #  detector's state file existed) -- no real P&L to
                    #  compute, so no debrief, same "skip when the data
                    #  isn't there" contract _fetch_exit_price already used.

        replayed = {sym: pos for sym, pos in replayed.items() if pos["qty"] > 1e-9}
        return closes, replayed

    def _debrief_close(
        self, symbol: str, entry_price: float, exit_price: float, qty: float, session_id: str,
    ) -> dict | None:
        realized_pnl = (exit_price - entry_price) * qty
        return self._write_debrief(symbol, entry_price, exit_price, qty, realized_pnl, session_id)

    def _debrief_snapshot_fallback(self, symbol: str, entry: dict, session_id: str) -> dict | None:
        exit_price = self._fetch_exit_price(symbol)
        if exit_price is None:
            return None
        qty = entry.get("qty", 0.0)
        avg_entry_price = entry.get("avg_entry_price", 0.0)
        realized_pnl = (exit_price - avg_entry_price) * qty
        return self._write_debrief(symbol, avg_entry_price, exit_price, qty, realized_pnl, session_id)

    def _write_debrief(
        self, symbol: str, entry_price: float, exit_price: float, qty: float,
        realized_pnl: float, session_id: str,
    ) -> dict:
        thesis_ids = self._fetch_open_thesis_ids(symbol)
        conclusion = "supports" if realized_pnl >= 0 else "contradicts"
        reasoning = (
            f"Position closed. Entry ~${entry_price:.2f}, exit ~${exit_price:.2f}, "
            f"qty {qty:g} -> realized P&L ${realized_pnl:.2f}."
        )

        updated = 0
        for hypothesis_id in thesis_ids:
            if self._write_evidence(hypothesis_id, realized_pnl, conclusion, reasoning):
                updated += 1

        # Significance-triage signal -- written regardless of whether the
        # evidence write above succeeded (a transient HypothesisRegistry
        # failure shouldn't also suppress the human-facing flag). Gated on
        # thesis_ids being non-empty: with no open thesis, there is nothing
        # for this close to have contradicted.
        if conclusion == "contradicts" and thesis_ids and self._ticker_ledger_store is not None:
            try:
                self._ticker_ledger_store.add_event(
                    ticker=symbol, stage="debrief", event_type="thesis_contradicted",
                    text=reasoning, ref_id=",".join(thesis_ids), source="watchlist",
                )
            except Exception:
                logger.debug("PositionCloseDetector: failed to write thesis_contradicted event", exc_info=True)

        try:
            from .kill_switch import AuditLogger

            AuditLogger.log(
                AuditLogger.JOURNAL_STATUS_CHANGED,
                details={"symbol": symbol, "realized_pnl": realized_pnl, "theses_updated": updated},
                session_id=session_id,
                symbol=symbol,
            )
        except Exception:
            pass

        return {"symbol": symbol, "realized_pnl": realized_pnl, "theses_updated": updated}

    def _fetch_exit_price(self, symbol: str) -> float | None:
        try:
            raw = self._registry.execute("get_stock_price", {"symbol": symbol})
        except Exception:
            return None
        from ..audit.ground_truth import _extract_latest_close

        return _extract_latest_close(raw)

    def _fetch_open_thesis_ids(self, symbol: str) -> list[str]:
        """Reads vinu-research's real hypotheses.json directly, in-process
        (see .research_link) -- no HTTP, since vinu-research is no longer
        assumed to be running as a separate service."""
        try:
            from .research_link import get_hypothesis_registry

            registry = get_hypothesis_registry()
            hypotheses = registry.query_by_symbol(symbol)
        except Exception:
            return []

        return [
            h.hypothesis_id for h in hypotheses
            if h.status.value in _ACTIVE_THESIS_STATUSES
        ]

    def _write_evidence(
        self, hypothesis_id: str | None, realized_pnl: float, conclusion: str, reasoning: str
    ) -> bool:
        if not hypothesis_id:
            return False

        try:
            from datetime import datetime, timezone

            from vinu_research.models import Evidence

            from .research_link import get_hypothesis_registry

            registry = get_hypothesis_registry()
            # run_id/iteration are 0 here (not from a backtest iteration) --
            # matches the real HTTP endpoint's own AddEvidenceRequest
            # defaults (server/routes_hypothesis.py), so this is the exact
            # same evidence shape the old HTTP call would have produced.
            updated = registry.add_evidence(hypothesis_id, Evidence(
                run_id=0,
                iteration=0,
                metric="realized_pnl",
                value=realized_pnl,
                conclusion=conclusion,
                reasoning=reasoning,
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))
            return updated is not None
        except Exception:
            return False
