from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from vinu_live.config import LiveConfig, load_config
from vinu_live.execution import compute_volume_profile, plan_twap, plan_vwap, schedule_slice_delays
from vinu_live.reconciliation import ReconciliationEngine
from vinu_live.signal_translator import SignalTranslator
from vinu_live.trade_plan.guards import (
    event_blackout_reason,
    fetch_spread_bps,
    halt_reason,
    spread_gate_reason_from_bps,
)
# Reuses the orchestrator's own MAX_SPREAD_BPS/EVENT_BLACKOUT_HOURS/
# MAX_SLIPPAGE_PCT/PASSIVE_LIMIT_OFFSET_BPS env-parsed thresholds and its
# _choose_entry_order_type decision, rather than defining a second,
# possibly-drifting copy of each -- both live paths should gate/route on
# the same spread/event/slippage tolerance. This closes the last piece of
# the execution-unification gap: this path used to always submit "market"
# regardless of spread, unlike the entry path's dynamic routing.
from vinu_live.trade_plan.orchestrator import (
    EVENT_BLACKOUT_HOURS,
    MAX_SLIPPAGE_PCT,
    MAX_SPREAD_BPS,
    PASSIVE_LIMIT_OFFSET_BPS,
    _choose_entry_order_type,
)

LOG = logging.getLogger(__name__)


class LiveScheduler:
    """Continuous trading cycle: fetch portfolio → translate → execute → reconcile.

    Follows the same `while True: cycle(); sleep(interval)` pattern used by
    every other worker process in the stack (news-ingest, stock-ingest, etc.).
    """

    def __init__(self, config: LiveConfig | None = None) -> None:
        self._config = config or load_config()
        try:
            from vinu_infra.auth import internal_auth_headers
            _headers = internal_auth_headers() or None
        except Exception:
            _headers = None
        self._http = httpx.AsyncClient(timeout=30.0, headers=_headers)
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

                submitted = await self._execute_plan(execution_plan, prices)
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
        resp = await self._http.get(f"{self._config.portfolio_api_url}/portfolio/state")
        resp.raise_for_status()
        return resp.json()

    async def _fetch_positions(self) -> dict[str, float]:
        """Current broker positions, keyed by symbol.

        Raises on failure -- same fail-closed posture as `_fetch_portfolio`.
        Silently returning {} here used to make an unreadable position list
        indistinguishable from a genuinely flat book, and that {} feeds
        straight into signal_translator.translate() as the current-holdings
        baseline: a real, unreported position would look like a fresh entry
        (order doubles up) and a needed reduce/exit would never be computed
        at all. The outer cycle() try/except aborts the whole cycle on this,
        which is the correct response to "we don't actually know what we
        hold" -- not "assume we hold nothing."
        """
        resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(
                f"Unexpected /agent/broker/positions response shape: {type(data).__name__}"
            )
        return {
            p.get("symbol", ""): float(p.get("qty", 0))
            for p in data if p.get("symbol")
        }

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
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
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
                    f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                    params={"interval": "15m", "days": 5, "adjusted": True},
                )
                if resp.status_code == 200:
                    bars = resp.json().get("data", [])
                    weights[symbol] = compute_volume_profile(bars, self._config.twap_slices)
            except Exception as e:
                LOG.warning("Could not fetch volume profile for %s, using equal weights: %s", symbol, e)
        return weights

    async def _execute_plan(self, plan: Any, prices: dict[str, float] | None = None) -> list[dict]:
        # Checks both the local HALT file AND the agent's cross-process kill
        # switch (see guards.halt_reason's docstring) -- this path used to
        # only check the local file, so a breaker/OOD-engaged remote halt
        # left the TWAP/VWAP loop cycling and failing orders instead of
        # stopping cleanly.
        _halt = await halt_reason(self._http, self._config.agent_api_url)
        if _halt:
            LOG.warning("Trading halted (%s) — skipping all order execution", _halt)
            return []
        prices = prices or {}
        submitted = []
        delays = schedule_slice_delays(
            plan.total_orders, total_window_minutes=60,
        )
        import time as _time

        for i, slice_ in enumerate(plan.slices):
            # Execution unification: this path used to fire straight to the
            # broker with no risk gates at all, unlike the signal-driven
            # entry path's spread/event-blackout checks. Same guards, same
            # fail-open posture, shared via guards.py rather than
            # duplicated -- a wide-spread or event-blackout symbol is
            # skipped (not submitted), remaining slices for OTHER symbols in
            # this plan still proceed.
            #
            # The spread is fetched once (not via spread_gate_reason's own
            # wrapper) so the same number also drives the order_type
            # decision below -- same "fetch once, reuse for gate + routing"
            # shape orchestrator.py's _maybe_enter already uses.
            _spread_bps = await fetch_spread_bps(self._http, self._config.stock_price_api_url, slice_.symbol)
            # A per-instruction max_slippage_pct budget (SignalTranslator's
            # own knob, previously set but never read by anything -- see
            # OrderInstruction.max_slippage_pct's docstring) tightens the
            # ceiling below the global default when it's the stricter of
            # the two; it never loosens it.
            _spread_ceiling = MAX_SPREAD_BPS
            if slice_.max_slippage_pct > 0:
                _spread_ceiling = min(MAX_SPREAD_BPS, slice_.max_slippage_pct * 10_000.0)
            _block_reason = spread_gate_reason_from_bps(_spread_bps, _spread_ceiling) or await event_blackout_reason(
                self._http, self._config.stock_price_api_url, slice_.symbol, EVENT_BLACKOUT_HOURS,
            )
            if _block_reason:
                LOG.warning(
                    "Skipping slice %d/%d for %s: %s",
                    slice_.slice_number, slice_.total_slices, slice_.symbol, _block_reason,
                )
                submitted.append({
                    "symbol": slice_.symbol, "side": slice_.side, "qty": slice_.qty,
                    "slice": slice_.slice_number, "status": "skipped", "reason": _block_reason,
                })
                if i < len(delays):
                    await asyncio.sleep(delays[i])
                continue

            # Dynamic per-order routing: this path used to hardcode "market"
            # regardless of spread, unlike the entry path -- same
            # _choose_entry_order_type decision, same slippage-budget
            # source (per-instruction if set, else the shared global
            # default). Falls back to "market" if the order_type comes back
            # "limit" but no price is known for this symbol (fail-open --
            # never submit a limit order with a guessed price).
            _slippage_budget = slice_.max_slippage_pct if slice_.max_slippage_pct > 0 else MAX_SLIPPAGE_PCT
            _order_type = _choose_entry_order_type(_spread_bps, _slippage_budget)
            _limit_price: float | None = None
            if _order_type == "limit":
                _price = prices.get(slice_.symbol)
                if _price is not None and _price > 0:
                    _offset = PASSIVE_LIMIT_OFFSET_BPS / 10_000.0
                    _limit_price = _price * (1 - _offset) if slice_.side == "buy" else _price * (1 + _offset)
                else:
                    _order_type = "market"

            # Idempotency (16): same minute-bucket key as orchestrator so a
            # retried slice dedupes on broker instead of double-filling.
            _bucket = int(_time.time() // 60)
            _cid = f"sched-{slice_.symbol}-{slice_.side}-{slice_.qty:.4f}-{slice_.slice_number}-{_bucket}"
            try:
                _payload = {
                    "symbol": slice_.symbol,
                    "side": slice_.side,
                    "qty": slice_.qty,
                    "order_type": _order_type,
                    "client_order_id": _cid,
                }
                if _limit_price is not None:
                    _payload["limit_price"] = _limit_price
                resp = await self._http.post(
                    f"{self._config.agent_api_url}/agent/broker/order",
                    json=_payload,
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
                _mid_halt = await halt_reason(self._http, self._config.agent_api_url)
                if _mid_halt:
                    LOG.warning(
                        "Trading halted mid-plan (%s) — stopping remaining %d slices",
                        _mid_halt, len(plan.slices) - i - 1,
                    )
                    break

        # Partial summary (16): slices already continue on failure above;
        # report partial so caller sees submitted vs failed, remainder is
        # retried next cycle via reconciler drift, never silently dropped.
        ok = sum(1 for s in submitted if s.get("status") == "submitted")
        bad = len(submitted) - ok
        if bad:
            LOG.warning("Partial fills: %d/%d slices submitted, %d failed — remainder next cycle", ok, len(submitted), bad)
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
            # Stage A (A3): same missing-price fix as SignalTranslator.
            # _build_instruction -- a fabricated expected position (from a
            # 1.0 price substitution) feeds reconciliation, which
            # auto-corrects drift, so a bad expected qty could trigger a
            # real corrective order. Skip an unpriceable symbol entirely
            # rather than inventing an expected position for it.
            price = prices.get(symbol)
            if price is None or price <= 0:
                LOG.warning(
                    "No usable price for %s -- excluding it from the expected-position "
                    "set this cycle so reconciliation doesn't act on a fabricated qty",
                    symbol,
                )
                continue
            target_value = tw.get("target_weight", 0.0) * portfolio_value
            expected[symbol] = target_value / price
        return expected
