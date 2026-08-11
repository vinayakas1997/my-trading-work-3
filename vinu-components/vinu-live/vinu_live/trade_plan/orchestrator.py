"""Phase 6: executes Phase 4's frozen trade plans against live data.

Reads ACTIVE `type=trade_plan` artifacts from vinu-research, enters a position when a plan is
approved and the book is flat for its symbol, evaluates contingency/invalidation rules against
live data for open positions, checks Phase 5's breaker before every single order attempt, and
reconciles Phase 3's book against the broker's actual positions at the end of every cycle. Zero
LLM calls -- every action here is a mechanical rule evaluation over a plan Phase 4 already
authored (see design decisions in the Phase 6 implementation doc). Deliberately does not import
`vinu_research.models` -- trade plans arrive as plain JSON dicts, preserving the 3-environment
isolation boundary.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np

from vinu_live.book.positions import (
    BookBackend,
    close_position,
    daily_realized_pnl,
    init_book,
    list_open_positions,
    open_position,
    reduce_position,
    update_stop_loss,
)
from vinu_live.book.schema import Position
from vinu_live.breaker.engine import BreakerVerdict, check_limits
from vinu_live.breaker.limits import BreakerState
from vinu_live.config import LiveConfig, load_config
from vinu_live.reconciliation import ReconciliationEngine
from vinu_live.trade_plan.condition_evaluator import find_triggered_rules
from vinu_live.trade_plan.live_metrics import compute_live_metrics
from vinu_live.trade_plan.rebalance_intake import RebalanceRequestQueue

LOG = logging.getLogger(__name__)

_COVARIANCE_WINDOW = 63
_RETURNS_LOOKBACK_DAYS = 90


class TradePlanOrchestrator:
    def __init__(
        self,
        config: LiveConfig | None = None,
        book: BookBackend | None = None,
        rebalance_queue: RebalanceRequestQueue | None = None,
    ) -> None:
        self._config = config or load_config()
        self._http = httpx.AsyncClient(timeout=30.0)
        self._book = book or init_book(str(self._config.data_root / "trade_plan_book.db"))
        self._breaker_state = BreakerState()
        self._reconciler = ReconciliationEngine()
        self._cycle_count = 0
        self._last_prices: dict[str, float] = {}
        # Phase 5: advisory intake for capital_allocator's rebalance
        # requests -- never a direct action, folded into the ordinary
        # per-cycle evaluation below, after the plan's own real
        # invalidation/contingency rules, never before them. SQLite-backed
        # at a shared, on-disk path (not per-instance in-memory) so a
        # request submitted via the HTTP intake route's own throwaway
        # TradePlanOrchestrator instance (server/app.py constructs a fresh
        # one per request) is still visible to the long-running
        # trade-plan-worker's orchestrator on its next real cycle.
        # Injectable (same DI pattern as `book` above) so tests get an
        # isolated queue instead of sharing config.data_root's real file.
        self._rebalance_queue = rebalance_queue or RebalanceRequestQueue(
            str(self._config.data_root / "rebalance_requests.db"),
        )
        # Phase 5: per-symbol debounce for the shock-angle trigger below --
        # monotonic clock, not wall time (immune to clock adjustments).
        self._last_shock_trigger: dict[str, float] = {}

    async def close(self) -> None:
        await self._http.aclose()
        self._book.close()
        self._rebalance_queue.close()

    def submit_rebalance_request(self, symbol: str, reason: str) -> None:
        """Called by whatever eventually implements capital_allocator's
        rebalancer (vinu-agent, a separate container) via this
        orchestrator's HTTP intake route -- see server/app.py. Accepting
        the request here only means it will be CONSIDERED on this
        symbol's next evaluation, not that it will be honored."""
        self._rebalance_queue.submit(symbol, reason)

    # Provisional, not tuned -- same "flag it, don't pretend it's settled"
    # discipline as _REBALANCE_PROTECT_GAIN_PCT above. Long enough that a
    # genuine burst of shock events (the exact scenario this trigger
    # exists to react to quickly) produces exactly one off-cycle check,
    # not one per event.
    _SHOCK_DEBOUNCE_SEC = 60.0

    async def on_shock_event(self, symbol: str) -> dict[str, Any] | None:
        """Off-cycle trigger (Phase 5, 01-plan.md item 3): shock_
        clustering/shock_personality fired for `symbol`. Runs the exact
        same per-symbol evaluation cycle() uses for its own per-plan loop,
        just off-schedule for this one symbol -- not a separate decision
        path. Debounced per symbol so a genuine burst of shock events
        produces exactly one check, not a cost-runaway (02-guard-rail.md).
        Returns None when debounced, no matching active plan, or no live
        price -- all silent no-ops by design (an off-cycle miss is
        recovered by the next scheduled cycle() regardless)."""
        symbol = symbol.upper()
        now = time.monotonic()
        last = self._last_shock_trigger.get(symbol)
        if last is not None and (now - last) < self._SHOCK_DEBOUNCE_SEC:
            return None
        self._last_shock_trigger[symbol] = now

        plans = await self._fetch_active_trade_plans()
        plan = next((p for p in plans if p.get("symbol") == symbol), None)
        if plan is None:
            return None

        prices = await self._fetch_prices([symbol])
        price = prices.get(symbol)
        if price is None:
            return None
        portfolio_value = await self._fetch_portfolio_value()

        position = self._find_open_position(symbol)
        if position is None:
            return await self._maybe_enter(plan, symbol, price, portfolio_value)
        return await self._evaluate_open_position(plan, position, price, portfolio_value)

    async def cycle(self) -> dict[str, Any]:
        self._cycle_count += 1
        cycle_id = f"tp_cycle_{self._cycle_count}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        LOG.info("[%s] Starting trade-plan cycle", cycle_id)

        result: dict[str, Any] = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "actions": [],
        }

        try:
            plans = await self._fetch_active_trade_plans()
            if not plans:
                result["status"] = "skipped_no_active_plans"
                return result

            symbols = sorted({p["symbol"] for p in plans if p.get("symbol")})
            prices = await self._fetch_prices(symbols)
            portfolio_value = await self._fetch_portfolio_value()

            actions: list[dict[str, Any]] = []
            for plan in plans:
                symbol = plan.get("symbol", "")
                price = prices.get(symbol)
                if not symbol or price is None:
                    LOG.warning("No live price for %s -- skipping this cycle", symbol)
                    continue

                position = self._find_open_position(symbol)
                if position is None:
                    action = await self._maybe_enter(plan, symbol, price, portfolio_value)
                else:
                    action = await self._evaluate_open_position(plan, position, price, portfolio_value)
                if action:
                    actions.append(action)

            result["actions"] = actions
            self._last_prices = prices

            recon = await self._reconcile_book_with_broker(prices)
            result["reconciliation"] = recon

        except Exception as e:
            LOG.error("[%s] Cycle failed: %s", cycle_id, e)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    # ------------------------------------------------------------------
    # Trade-plan fetching
    # ------------------------------------------------------------------

    async def _fetch_active_trade_plans(self) -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/artifacts",
                params={"status": "ACTIVE", "type_": "trade_plan"},
            )
            if resp.status_code != 200:
                return []
            summaries = resp.json()
        except Exception as e:
            LOG.warning("Failed to list active trade plans: %s", e)
            return []

        plans: list[dict[str, Any]] = []
        for summary in summaries:
            artifact_id = summary.get("artifact_id")
            if not artifact_id:
                continue
            try:
                detail_resp = await self._http.get(
                    f"{self._config.research_api_url}/research/trade-plan/{artifact_id}",
                )
                if detail_resp.status_code != 200:
                    continue
                raw = detail_resp.json().get("trade_plan_data")
                if not raw:
                    continue
                plan = json.loads(raw)
                plan["_artifact_id"] = artifact_id
                plans.append(plan)
            except Exception as e:
                LOG.warning("Failed to fetch trade plan %s: %s", artifact_id, e)
        return plans

    # ------------------------------------------------------------------
    # Entry
    # ------------------------------------------------------------------

    async def _maybe_enter(
        self, plan: dict[str, Any], symbol: str, price: float, portfolio_value: float,
    ) -> dict[str, Any] | None:
        direction = plan.get("direction", "neutral")
        if direction not in ("long", "short"):
            return None

        size_pct = (plan.get("risk_bands") or {}).get("max_position_size_pct", 0.0) or 0.0
        if size_pct <= 0:
            LOG.info("Trade plan for %s has no position size -- skipping entry", symbol)
            return None

        qty = (size_pct * portfolio_value) / price
        if qty <= 0:
            return None

        verdict, reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT -- skipping entry for %s: %s", symbol, reason)
            return {"symbol": symbol, "action": "entry_blocked_by_breaker", "reason": reason}

        side = "buy" if direction == "long" else "sell"
        order_result = await self._submit_order(symbol, side, qty)
        if order_result.get("status") == "submitted":
            open_position(self._book, symbol, direction, qty, price, artifact_id=plan.get("_artifact_id", ""))
            LOG.info("Entered %s %s %.4f @ %.2f", direction, symbol, qty, price)
            return {"symbol": symbol, "action": "entered", "direction": direction, "qty": qty, "price": price}

        LOG.info(
            "Entry not filled for %s: broker status=%s", symbol, order_result.get("status"),
        )
        return {"symbol": symbol, "action": "entry_not_filled", "broker_status": order_result.get("status")}

    # ------------------------------------------------------------------
    # Open-position evaluation
    # ------------------------------------------------------------------

    async def _fetch_calibration_accuracy(self, artifact_id: str) -> float | None:
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/trade-plan/{artifact_id}/calibration",
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            n = data.get("n_entries", 0)
            if n < 5:
                return None
            return data.get("accuracy")
        except Exception as e:
            LOG.debug("Failed to fetch calibration for %s: %s", artifact_id, e)
        return None

    async def _evaluate_open_position(
        self, plan: dict[str, Any], position: Position, price: float, portfolio_value: float,
    ) -> dict[str, Any] | None:
        symbol = position.symbol
        previous_close = self._last_prices.get(symbol)
        recent_prices = await self._fetch_recent_prices(symbol)
        recent_returns = _simple_returns(recent_prices)
        cluster_corr = await self._fetch_shock_cluster_correlation(symbol)

        artifact_id = plan.get("_artifact_id", "")
        calibration_accuracy = await self._fetch_calibration_accuracy(artifact_id) if artifact_id else None

        created_at = plan.get("created_at", "")
        days_elapsed = 0
        if created_at:
            try:
                created = datetime.fromisoformat(created_at)
                days_elapsed = (datetime.now(timezone.utc) - created).days
            except (ValueError, TypeError):
                pass

        metrics = compute_live_metrics(
            position, price, plan,
            recent_returns=recent_returns,
            previous_close=previous_close,
            shock_cluster_correlation=cluster_corr,
            calibration_accuracy=calibration_accuracy,
            days_elapsed=days_elapsed,
        )

        triggered_invalidations = find_triggered_rules(
            plan.get("invalidation_conditions") or [], metrics,
        )
        if triggered_invalidations:
            return await self._apply_invalidation(
                position, price, portfolio_value, triggered_invalidations[0],
            )

        triggered_contingencies = find_triggered_rules(
            plan.get("contingency_rules") or [], metrics,
        )
        if triggered_contingencies:
            return await self._apply_contingency(
                position, price, portfolio_value, triggered_contingencies[0],
            )

        rebalance_request = self._rebalance_queue.pending_for(symbol)
        if rebalance_request is not None:
            return await self._evaluate_rebalance_request(
                position, price, portfolio_value, rebalance_request,
            )

        LOG.info("No rule triggered for %s -- holding unchanged", symbol)
        return {"symbol": symbol, "action": "hold", "reason": "no_rule_triggered"}

    # Provisional threshold, not tuned -- same "flag it, don't pretend
    # it's settled" discipline as this build's other not-yet-tuned
    # constants (N/K caps, completeness tolerance, PBO bands). Protects a
    # real winner from being unwound just to satisfy a reallocation ask;
    # a position within this band has little cost to giving up now.
    _REBALANCE_PROTECT_GAIN_PCT = 0.05

    async def _evaluate_rebalance_request(
        self, position: Position, price: float, portfolio_value: float, request: Any,
    ) -> dict[str, Any]:
        """The rebalance request is advisory input ONLY -- this method is
        reached exclusively when the plan's own real invalidation/
        contingency rules found nothing to act on (see
        _evaluate_open_position above). It can still decline: a real
        unrealized gain beyond _REBALANCE_PROTECT_GAIN_PCT is a real
        reason to hold, not honor the request, matching 02-guard-rail.md's
        'orchestrator retains final say.'"""
        symbol = position.symbol
        self._rebalance_queue.consume(symbol)  # considered once, either way

        favorable_move_pct = (
            (price - position.avg_entry) / position.avg_entry if position.side == "long"
            else (position.avg_entry - price) / position.avg_entry
        ) if position.avg_entry > 0 else 0.0

        if favorable_move_pct > self._REBALANCE_PROTECT_GAIN_PCT:
            LOG.info(
                "Declining rebalance request for %s -- unrealized gain %.2f%% protects the position",
                symbol, favorable_move_pct * 100,
            )
            return {
                "symbol": symbol, "action": "rebalance_declined",
                "reason": request.reason, "unrealized_gain_pct": favorable_move_pct,
            }

        verdict, breaker_reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT -- skipping rebalance reduce for %s: %s", symbol, breaker_reason)
            return {"symbol": symbol, "action": "rebalance_blocked_by_breaker", "reason": breaker_reason}

        reduce_qty = position.qty * 0.5
        side = "sell" if position.side == "long" else "buy"
        order_result = await self._submit_order(symbol, side, reduce_qty)
        if order_result.get("status") == "submitted":
            reduce_position(self._book, position.position_id, reduce_qty, price)
            LOG.info("Honored rebalance request for %s (reason: %s)", symbol, request.reason)
            return {
                "symbol": symbol, "action": "rebalance_honored",
                "qty": reduce_qty, "reason": request.reason,
            }

        LOG.info("Rebalance reduce not filled for %s: broker status=%s", symbol, order_result.get("status"))
        return {
            "symbol": symbol, "action": "rebalance_not_filled",
            "broker_status": order_result.get("status"), "reason": request.reason,
        }

    async def _apply_invalidation(
        self, position: Position, price: float, portfolio_value: float, rule: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = position.symbol
        verdict, reason = await self._check_breaker(portfolio_value)
        if verdict == BreakerVerdict.HALT:
            LOG.warning("Breaker HALT -- skipping invalidation exit for %s: %s", symbol, reason)
            return {"symbol": symbol, "action": "exit_blocked_by_breaker", "reason": reason, "rule": rule}

        side = "sell" if position.side == "long" else "buy"
        order_result = await self._submit_order(symbol, side, position.qty)
        if order_result.get("status") == "submitted":
            close_position(self._book, position.position_id, price)
            LOG.info("Invalidation exit for %s (rule: %s)", symbol, rule.get("condition"))
            return {"symbol": symbol, "action": "invalidation_exit", "rule": rule}

        LOG.info("Invalidation exit not filled for %s: broker status=%s", symbol, order_result.get("status"))
        return {"symbol": symbol, "action": "exit_not_filled", "broker_status": order_result.get("status"), "rule": rule}

    async def _apply_contingency(
        self, position: Position, price: float, portfolio_value: float, rule: dict[str, Any],
    ) -> dict[str, Any]:
        symbol = position.symbol
        action = rule.get("action")
        params = rule.get("action_params") or {}

        if action == "tighten_stop":
            tighten_pct = params.get("tighten_by_pct", 0.3)
            favorable_move = (price - position.avg_entry) if position.side == "long" else (position.avg_entry - price)
            offset = max(favorable_move, 0.0) * tighten_pct
            new_stop = price - offset if position.side == "long" else price + offset
            update_stop_loss(self._book, position.position_id, new_stop)
            LOG.info("Tightened stop for %s to %.2f (rule: %s)", symbol, new_stop, rule.get("condition"))
            return {"symbol": symbol, "action": "tighten_stop", "new_stop": new_stop, "rule": rule}

        if action == "reduce_position":
            reduce_pct = params.get("reduce_by_pct", 0.5)
            reduce_qty = position.qty * reduce_pct
            verdict, reason = await self._check_breaker(portfolio_value)
            if verdict == BreakerVerdict.HALT:
                LOG.warning("Breaker HALT -- skipping reduce for %s: %s", symbol, reason)
                return {"symbol": symbol, "action": "reduce_blocked_by_breaker", "reason": reason, "rule": rule}

            side = "sell" if position.side == "long" else "buy"
            order_result = await self._submit_order(symbol, side, reduce_qty)
            if order_result.get("status") == "submitted":
                reduce_position(self._book, position.position_id, reduce_qty, price)
                LOG.info("Reduced %s by %.4f (rule: %s)", symbol, reduce_qty, rule.get("condition"))
                return {"symbol": symbol, "action": "reduce_position", "qty": reduce_qty, "rule": rule}

            LOG.info("Reduce not filled for %s: broker status=%s", symbol, order_result.get("status"))
            return {"symbol": symbol, "action": "reduce_not_filled", "broker_status": order_result.get("status"), "rule": rule}

        LOG.warning(
            "Unhandled contingency action %r for %s -- no matching handler, holding "
            "unchanged (explicit, not a silent no-op)", action, symbol,
        )
        return {"symbol": symbol, "action": "unhandled_contingency", "rule": rule}

    # ------------------------------------------------------------------
    # Breaker
    # ------------------------------------------------------------------

    async def _check_breaker(self, portfolio_value: float) -> tuple[str, str | None]:
        positions = list_open_positions(self._book)
        symbols = sorted({p.symbol for p in positions})
        prices = await self._fetch_prices(symbols) if symbols else {}
        daily_pnl = daily_realized_pnl(self._book)
        covariance_matrix = await self._compute_covariance(symbols) if len(symbols) >= 2 else None
        return check_limits(
            self._book,
            prices=prices,
            portfolio_value=portfolio_value,
            daily_realized_pnl=daily_pnl,
            covariance_matrix=covariance_matrix,
            cluster_map=None,
            state=self._breaker_state,
        )

    async def _compute_covariance(self, symbols: list[str]) -> np.ndarray | None:
        from vinu_tools.compute.risk.covariance import dynamic_covariance

        price_series = await asyncio.gather(*(self._fetch_recent_prices(s) for s in symbols))
        min_len = min((len(p) for p in price_series), default=0)
        if min_len < 20:
            return None
        aligned = np.array([p[-min_len:] for p in price_series])
        cov = dynamic_covariance(aligned, window=_COVARIANCE_WINDOW, use_shrinkage=True)
        if np.any(np.isnan(cov)):
            return None
        return cov

    # ------------------------------------------------------------------
    # Broker / market data
    # ------------------------------------------------------------------

    def _find_open_position(self, symbol: str) -> Position | None:
        positions = list_open_positions(self._book, symbol=symbol)
        return positions[0] if positions else None

    async def _submit_order(self, symbol: str, side: str, qty: float) -> dict[str, Any]:
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/broker/order",
                json={"symbol": symbol, "side": side, "qty": qty, "order_type": "market"},
            )
            if resp.status_code != 200:
                return {"status": "error", "http_status": resp.status_code}
            return resp.json()
        except Exception as e:
            LOG.warning("Order submission failed for %s: %s", symbol, e)
            return {"status": "error", "error": str(e)}

    async def _fetch_prices(self, symbols: list[str]) -> dict[str, float]:
        prices: dict[str, float] = {}
        for symbol in symbols:
            try:
                resp = await self._http.get(
                    f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                    params={"interval": "1d", "days": 5, "adjusted": True},
                )
                if resp.status_code == 200:
                    bars = resp.json().get("data", [])
                    if bars:
                        prices[symbol] = float(bars[-1].get("close", 0.0))
            except Exception as e:
                LOG.warning("Could not fetch price for %s: %s", symbol, e)
        return prices

    async def _fetch_recent_prices(self, symbol: str, days: int = _RETURNS_LOOKBACK_DAYS) -> list[float]:
        try:
            resp = await self._http.get(
                f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "days": days, "adjusted": True},
            )
            if resp.status_code == 200:
                bars = resp.json().get("data", [])
                return [float(b["close"]) for b in bars if b.get("close")]
        except Exception as e:
            LOG.warning("Could not fetch recent prices for %s: %s", symbol, e)
        return []

    async def _fetch_portfolio_value(self) -> float:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
            if resp.status_code == 200:
                account = resp.json()
                if account.get("configured") and account.get("equity") is not None:
                    return float(account["equity"])
        except Exception as e:
            LOG.warning("Could not fetch account equity: %s", e)
        LOG.warning(
            "No broker account configured -- using fallback_portfolio_value=%.2f",
            self._config.fallback_portfolio_value,
        )
        return self._config.fallback_portfolio_value

    async def _fetch_shock_cluster_correlation(self, symbol: str) -> float | None:
        try:
            resp = await self._http.get(
                f"{self._config.initial_analysis_api_url}/analysis/angle/shock_clustering/{symbol}",
            )
            if resp.status_code != 200:
                return None
            rows = resp.json().get("data", [])
            if not rows:
                return None
            members = (rows[-1] or {}).get("cluster_members") or []
            correlations = [abs(m.get("shock_correlation", 0.0)) for m in members]
            return max(correlations) if correlations else None
        except Exception as e:
            LOG.warning("Could not fetch shock cluster correlation for %s: %s", symbol, e)
            return None

    # ------------------------------------------------------------------
    # Reconciliation — Phase 3's book is never left reflecting an assumed state
    # ------------------------------------------------------------------

    async def _reconcile_book_with_broker(self, prices: dict[str, float]) -> dict[str, Any]:
        expected = {p.symbol: (p.qty if p.side == "long" else -p.qty) for p in list_open_positions(self._book)}
        actual = await self._fetch_broker_positions()
        portfolio_value = sum(abs(q) * prices.get(sym, 0.0) for sym, q in expected.items()) or 1.0
        report = self._reconciler.reconcile(expected, actual, portfolio_value)
        if report.drift_detected:
            LOG.warning(
                "Book/broker drift detected: %d symbol(s), %.2f%% total",
                len(report.symbol_drifts), report.total_drift_pct,
            )
        return {
            "drift_detected": report.drift_detected,
            "n_drifts": len(report.symbol_drifts),
            "total_drift_pct": report.total_drift_pct,
        }

    async def _fetch_broker_positions(self) -> dict[str, float]:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return {
                        p.get("symbol", ""): float(p.get("qty", 0))
                        for p in data if p.get("symbol")
                    }
        except Exception as e:
            LOG.warning("Could not fetch broker positions: %s", e)
        return {}


def _simple_returns(prices: list[float]) -> list[float]:
    if len(prices) < 2:
        return []
    return [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] != 0
    ]
