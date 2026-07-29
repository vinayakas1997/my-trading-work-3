from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from vinu_live.config import LiveConfig, load_config
from vinu_live.execution import compute_volume_profile, plan_twap, plan_vwap, schedule_slice_delays
from vinu_live.reconciliation import ReconciliationEngine
from vinu_live.signal_translator import SignalTranslator

LOG = logging.getLogger(__name__)


class LiveScheduler:
    """Continuous trading cycle: fetch portfolio → translate → execute → reconcile.

    Follows the same `while True: cycle(); sleep(interval)` pattern used by
    every other worker process in the stack (news-ingest, stock-ingest, etc.).
    """

    def __init__(self, config: LiveConfig | None = None) -> None:
        self._config = config or load_config()
        self._http = httpx.AsyncClient(timeout=30.0)
        self._translator = SignalTranslator(max_slippage_pct=self._config.max_slippage_pct)
        self._reconciler = ReconciliationEngine()
        self._cycle_count = 0

    async def close(self) -> None:
        await self._http.aclose()

    async def cycle(self) -> dict[str, Any]:
        """Execute one full trading cycle.

        Returns a dict with cycle results for logging/monitoring.
        """
        self._cycle_count += 1
        cycle_id = f"cycle_{self._cycle_count}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        LOG.info("[%s] Starting trading cycle", cycle_id)

        result: dict[str, Any] = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
        }

        try:
            portfolio = await self._fetch_portfolio()
            if portfolio.get("status") == "empty":
                LOG.info("[%s] No active strategies — skipping", cycle_id)
                result["status"] = "skipped_no_strategies"
                return result

            target_weights = portfolio.get("weights", [])
            if not target_weights:
                LOG.info("[%s] No target weights — skipping", cycle_id)
                result["status"] = "skipped_no_weights"
                return result

            current_positions = await self._fetch_positions()
            prices = await self._fetch_prices(target_weights)
            portfolio_value = await self._fetch_portfolio_value(current_positions, prices)

            instructions = self._translator.translate(
                target_weights, current_positions, portfolio_value, prices,
            )
            result["n_instructions"] = len(instructions)

            if instructions:
                execution_plan = await self._plan_execution(instructions)
                result["n_slices"] = execution_plan.total_orders

                submitted = await self._execute_plan(execution_plan)
                result["submitted"] = submitted

            expected_positions = self._compute_expected_positions(
                target_weights, prices, portfolio_value,
            )
            recon_report = self._reconciler.reconcile(
                expected_positions, current_positions, portfolio_value,
            )
            result["reconciliation"] = {
                "drift_detected": recon_report.drift_detected,
                "n_drifts": len(recon_report.symbol_drifts),
                "total_drift_pct": recon_report.total_drift_pct,
            }

        except Exception as e:
            LOG.error("[%s] Cycle failed: %s", cycle_id, e)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    async def _fetch_portfolio(self) -> dict[str, Any]:
        resp = await self._http.get(f"{self._config.portfolio_api_url}/state")
        resp.raise_for_status()
        return resp.json()

    async def _fetch_positions(self) -> dict[str, float]:
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/broker/positions")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list):
                    return {
                        p.get("symbol", ""): float(p.get("qty", 0))
                        for p in data if p.get("symbol")
                    }
        except Exception as e:
            LOG.warning("Could not fetch positions: %s", e)
        return {}

    async def _fetch_prices(self, target_weights: list[dict]) -> dict[str, float]:
        """Latest close per symbol from vinu-stock-price directly.

        Previously called a `/prices/{symbol}` route on agent-api that was
        never implemented — every call silently fell back to a price of 1.0,
        which made every downstream qty/value computation nonsense. agent-api
        owns the broker connection, not price data, so this goes straight to
        the service that actually has it.
        """
        prices: dict[str, float] = {}
        for tw in target_weights:
            symbol = tw.get("symbol", "")
            if not symbol:
                continue
            try:
                resp = await self._http.get(
                    f"{self._config.stock_price_api_url}/candles/{symbol}",
                    params={"interval": "1d", "days": 5, "adjusted": True},
                )
                if resp.status_code == 200:
                    bars = resp.json().get("data", [])
                    if bars:
                        prices[symbol] = float(bars[-1].get("close", 0.0))
            except Exception as e:
                LOG.warning("Could not fetch price for %s: %s", symbol, e)
        return prices

    async def _fetch_portfolio_value(
        self, current_positions: dict[str, float], prices: dict[str, float],
    ) -> float:
        """Live account equity from agent-api's /broker/account.

        Previously fell back to a hardcoded $1,000,000 whenever the (sum of
        positions * price) computation was falsy — including the common case
        of zero current positions, which is not actually an error, just an
        empty portfolio, but the fallback masked it as a fabricated $1M
        balance. Now sizing is based on the real account, and the fallback is
        explicit config, logged loudly, not a silent magic number.
        """
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/broker/account")
            if resp.status_code == 200:
                account = resp.json()
                if account.get("configured") and account.get("equity") is not None:
                    return float(account["equity"])
        except Exception as e:
            LOG.warning("Could not fetch account equity: %s", e)

        positions_value = sum(
            qty * prices.get(sym, 0.0) for sym, qty in current_positions.items()
        )
        if positions_value > 0:
            return positions_value

        LOG.warning(
            "No broker account configured and no priced positions — using "
            "fallback_portfolio_value=%.2f for sizing. This is a placeholder, "
            "not real capital.",
            self._config.fallback_portfolio_value,
        )
        return self._config.fallback_portfolio_value

    async def _plan_execution(self, instructions: list[Any]) -> Any:
        if self._config.execution_style == "vwap":
            volume_weights = await self._fetch_volume_weights(instructions)
            return plan_vwap(instructions, volume_weights=volume_weights, n_slices=self._config.twap_slices)
        return plan_twap(instructions, n_slices=self._config.twap_slices)

    async def _fetch_volume_weights(self, instructions: list[Any]) -> dict[str, list[float]]:
        weights: dict[str, list[float]] = {}
        for instr in instructions:
            symbol = instr.symbol
            if symbol in weights:
                continue
            try:
                resp = await self._http.get(
                    f"{self._config.stock_price_api_url}/candles/{symbol}",
                    params={"interval": "15m", "days": 5, "adjusted": True},
                )
                if resp.status_code == 200:
                    bars = resp.json().get("data", [])
                    weights[symbol] = compute_volume_profile(bars, self._config.twap_slices)
            except Exception as e:
                LOG.warning("Could not fetch volume profile for %s, using equal weights: %s", symbol, e)
        return weights

    async def _execute_plan(self, plan: Any) -> list[dict]:
        HALT_PATH = Path.home() / ".vinu-live" / "HALT"
        if HALT_PATH.exists():
            LOG.warning("HALT file detected at %s — skipping all order execution", HALT_PATH)
            return []
        submitted = []
        delays = schedule_slice_delays(
            plan.total_orders, total_window_minutes=60,
        )
        for i, slice_ in enumerate(plan.slices):
            try:
                resp = await self._http.post(
                    f"{self._config.agent_api_url}/broker/order",
                    json={
                        "symbol": slice_.symbol,
                        "side": slice_.side,
                        "qty": slice_.qty,
                        "order_type": "market",
                    },
                )
                result = {
                    "symbol": slice_.symbol,
                    "side": slice_.side,
                    "qty": slice_.qty,
                    "slice": slice_.slice_number,
                    "status": "submitted" if resp.status_code < 400 else "failed",
                }
                submitted.append(result)
                LOG.info(
                    "Submitted %s %s %s (slice %d/%d)",
                    slice_.side, slice_.qty, slice_.symbol,
                    slice_.slice_number, slice_.total_slices,
                )
            except Exception as e:
                LOG.warning("Order submission failed: %s", e)
                submitted.append({
                    "symbol": slice_.symbol,
                    "side": slice_.side,
                    "qty": slice_.qty,
                    "slice": slice_.slice_number,
                    "status": "error",
                    "error": str(e),
                })

            if i < len(delays):
                await asyncio.sleep(delays[i])
                if HALT_PATH.exists():
                    LOG.warning("HALT file detected mid-plan — stopping remaining %d slices", len(plan.slices) - i - 1)
                    break

        return submitted

    @staticmethod
    def _compute_expected_positions(
        target_weights: list[dict],
        prices: dict[str, float],
        portfolio_value: float,
    ) -> dict[str, float]:
        expected: dict[str, float] = {}
        for tw in target_weights:
            symbol = tw.get("symbol", "")
            if not symbol:
                continue
            target_value = tw.get("target_weight", 0.0) * portfolio_value
            price = prices.get(symbol, 1.0)
            expected[symbol] = target_value / price if price > 0 else 0.0
        return expected
