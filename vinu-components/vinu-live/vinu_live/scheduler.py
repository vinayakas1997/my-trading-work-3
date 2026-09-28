from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from vinu_infra.maturity_consultation import MaturityConsultationStore
from vinu_live.book.positions import daily_realized_pnl, init_book
from vinu_live.breaker.engine import BreakerVerdict, check_limits
from vinu_live.breaker.limits import DEFAULT_LIMITS, BreakerLimits, BreakerState
from vinu_live.config import LiveConfig, load_config
from vinu_live.execution import compute_volume_profile, plan_twap, plan_vwap, schedule_slice_delays
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    list_open_positions,
    list_unapplied_executes,
    mark_decision_applied,
    open_position,
)
from vinu_live.maturity_link import fetch_maturity_status, scale_limits_for_tier
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

# item #24 finding #3 fix (system-wide-audit-and-design/02-open-questions-
# strategy-and-simulation.md): how many consecutive cycles a symbol's
# expected-vs-actual drift must persist before it's alert-worthy. Unlike
# orchestrator.py's book-vs-broker check (external drift between cycles --
# a partial fill, a manual trade), THIS reconciliation compares a
# just-changed target against positions fetched before this same cycle's
# own orders were even submitted, so some drift every cycle is the
# expected gap those orders are already closing, not an anomaly -- see
# _handle_reconciliation_drift's own docstring. Guessed starting constant,
# same posture (and same number) as item #23 finding #4's
# consecutive_unavailable_count, meant to be revisited once real data
# exists.
RECON_DRIFT_ALERT_CYCLES = 3


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
        # item #24 finding #1 (system-wide-audit-and-design/
        # 02-open-questions-strategy-and-simulation.md): this loop used to
        # never call check_limits() at all -- the main portfolio-rebalance
        # path could blindly execute weights past a real daily-loss/VaR/
        # leverage/cluster-exposure/position-count breach. Same book path
        # orchestrator.py/feedback_loop.py already use (SQLite-backed at a
        # shared, on-disk path -- a second BookBackend instance pointed at
        # the same file is safe, same reasoning server/app.py's rebalance-
        # request route already documents for a different store). Own
        # in-memory BreakerState, same pattern orchestrator.py uses (one
        # per long-lived worker instance) -- a fresh HALT verdict is made
        # cross-process-visible via _engage_real_halt(), not by sharing
        # this Python object, which is impossible across processes anyway.
        self._book = init_book(str(self._config.data_root / "trade_plan_book.db"))
        self._breaker_state = BreakerState()
        # Point 7 option 1 (reverse-engineering/06-execution-handoff-and-
        # architecture.md): the same on-disk live_decision.db the poller
        # (live_decision/poller.py) and vinu-live's own HTTP routes
        # already read/write -- a second LiveDecisionBackend instance
        # pointed at the same file is safe, same reasoning already
        # applied to self._book above.
        self._live_decision_backend = LiveDecisionBackend(str(self._config.data_root / "live_decision.db"))
        # item #24 finding #3: per-symbol consecutive-drift streak +
        # edge-triggered notified set, same in-memory-per-worker-instance
        # shape as self._breaker_state above -- see
        # _handle_reconciliation_drift's own docstring for why a streak,
        # not "notify on any drift".
        self._recon_drift_streak: dict[str, int] = {}
        self._recon_drift_notified: set[str] = set()
        # high-expectations follow-up, points #2/#3: one shared, queryable
        # log of every maturity-tier consultation across every consumer in
        # this codebase (not one log per consumer -- see
        # maturity_consultation.py's own module docstring). Same on-disk-
        # SQLite-instance-per-worker pattern as self._book/
        # self._live_decision_backend above.
        self._maturity_consultation_store = MaturityConsultationStore(
            str(self._config.data_root / "maturity_consultations.db"),
        )

    async def close(self) -> None:
        await self._http.aclose()
        self._book.close()
        self._live_decision_backend.close()
        self._maturity_consultation_store.close()

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
            target_weights = [] if portfolio.get("status") == "empty" else portfolio.get("weights", [])

            # Point 7 option 1 (06-execution-handoff-and-architecture.md):
            # fold any live_decision_agent EXECUTE verdicts not yet acted
            # on into this cycle's target_weights, same list the normal
            # portfolio-rebalance weights flow through -- so they gain
            # this loop's existing risk-limit check (_check_breaker) and
            # same-symbol netting (SignalTranslator._net_by_symbol) "for
            # free" rather than needing a second gate stack, per that
            # design doc's own recommended default.
            live_decision_weights = await self._fetch_live_decision_weights(cycle_id)
            target_weights = target_weights + live_decision_weights

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
                # item #24 finding #1: real risk-limit check (daily loss,
                # VaR, leverage, cluster exposure, position count) before
                # any order is planned/submitted -- this loop used to
                # never call this at all, unlike the orchestrator's own
                # entry/exit paths.
                breaker_verdict, breaker_reason = await self._check_breaker(portfolio_value)
                if breaker_verdict == BreakerVerdict.HALT:
                    LOG.warning(
                        "[%s] Breaker HALT -- skipping all order planning/execution this cycle: %s",
                        cycle_id, breaker_reason,
                    )
                    result["status"] = "halted_by_breaker"
                    result["breaker_reason"] = breaker_reason
                else:
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
            # item #24 finding #3: this report used to be built and put in
            # `result` for whoever reads the cycle's return value, but
            # `cli.py::worker_main` only ever logged the overall status,
            # never inspected it -- a real drift was silently absorbed
            # into a dict nobody read. Now wired through the same notify
            # path orchestrator.py's own book-vs-broker drift already uses.
            await self._handle_reconciliation_drift(recon_report)

        except Exception as e:
            LOG.error("[%s] Cycle failed: %s", cycle_id, e)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    async def _maturity_scaled_limits(self) -> BreakerLimits | None:
        """high-expectations follow-up, point #2 (risk_gatekeeper consults
        the system maturity tier). Opt-in via
        `risk_gatekeeper_maturity_scaling_enabled` -- off by default, same
        cautious-rollout posture as every other maturity-tier consumer in
        this codebase. Returns None when disabled or on any failure, which
        `check_limits()` already treats as "use DEFAULT_LIMITS" -- fails
        open to the unscaled limits, never fails closed by inventing a
        stricter default of its own."""
        if not self._config.risk_gatekeeper_maturity_scaling_enabled:
            return None
        status = await fetch_maturity_status(self._http, self._config.research_api_url)
        if status is None:
            self._maturity_consultation_store.record(
                service="vinu-live", consumer="risk_gatekeeper", tier="unknown",
                action_taken="no_change_status_unavailable",
            )
            return None
        tier = status.get("tier", "mature")
        scaled = scale_limits_for_tier(DEFAULT_LIMITS, tier)
        action = "no_change_already_mature" if tier == "mature" else f"limits_scaled_{tier}"
        self._maturity_consultation_store.record(
            service="vinu-live", consumer="risk_gatekeeper", tier=tier,
            action_taken=action, evidence=status,
        )
        return scaled

    async def _check_breaker(self, portfolio_value: float) -> tuple[str, str | None]:
        """Same shape as trade_plan/orchestrator.py's own _check_breaker --
        deliberately not covariance-aware yet (passes covariance_matrix=
        None, same as that method's own <2-symbol fallback): the real
        _compute_covariance is a 90-day-candle-fetch-plus-shrinkage
        calculation tightly coupled to the orchestrator's own caching, not
        yet extracted into something both paths can share. check_limits()
        already treats a None covariance matrix as "skip the aggregate-VaR
        check" (breaker/engine.py::_check_aggregate_var), not a crash --
        every other check (daily loss, position count, cluster exposure,
        leverage) still runs in full. A real, scoped gap, not hidden."""
        from vinu_live.book.positions import list_open_positions

        positions = list_open_positions(self._book)
        symbols = sorted({p.symbol for p in positions})
        prices = await self._fetch_prices([{"symbol": s} for s in symbols]) if symbols else {}
        daily_pnl = daily_realized_pnl(self._book)
        was_halted = self._breaker_state.halted
        limits = await self._maturity_scaled_limits()
        verdict, reason = check_limits(
            self._book,
            prices=prices,
            portfolio_value=portfolio_value,
            daily_realized_pnl=daily_pnl,
            covariance_matrix=None,
            cluster_map=None,
            limits=limits,
            state=self._breaker_state,
        )
        if verdict == BreakerVerdict.HALT and not was_halted:
            # Mirrors orchestrator.py's _engage_real_halt: this process's
            # own in-memory BreakerState flip is invisible to every other
            # process (this loop, the orchestrator, OrderGuard) -- the
            # real, persistent, cross-process kill switch is what
            # scheduler._execute_plan's own halt_reason() check already
            # reads from.
            await self._engage_real_halt(reason)
        return verdict, reason

    async def _engage_real_halt(self, reason: str | None) -> None:
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/broker/halt",
                json={"reason": f"breaker: {reason}"},
            )
            if getattr(resp, "status_code", None) == 200:
                LOG.warning("BREAKER HALT -- engaged the real kill switch via %s (%s)",
                            self._config.agent_api_url, reason)
            else:
                LOG.error(
                    "BREAKER HALT -- FAILED to engage the real kill switch via %s "
                    "(http %s) -- other order paths are NOT halted: %s",
                    self._config.agent_api_url, getattr(resp, "status_code", "?"), reason,
                )
        except Exception as e:  # noqa: BLE001
            LOG.error(
                "BREAKER HALT -- FAILED to engage the real kill switch via %s -- "
                "other order paths are NOT halted: %s (%s)",
                self._config.agent_api_url, reason, e,
            )

    async def _handle_reconciliation_drift(self, recon_report: Any) -> None:
        """item #24 finding #3's fix. Deliberately NOT "notify on any
        drift": this reconciliation compares this cycle's just-computed
        `expected_positions` (from the target weights this same cycle
        just decided on) against `current_positions` fetched before this
        cycle's own orders were even submitted -- so on a normal cycle
        where a target changed, some drift is the expected gap those
        orders are already closing, not an anomaly. Alerting on that
        would just be noise on every rebalance.

        Instead, same fix shape as item #23 finding #4's
        `consecutive_unavailable_count`: track how many consecutive
        cycles each symbol has shown drift, and only alert once a streak
        crosses `RECON_DRIFT_ALERT_CYCLES` -- meaning this cycle's own
        orders aren't actually closing the gap either, a real problem
        (stuck order, unpriceable symbol, a halt). Edge-triggered, same
        as orchestrator.py's own `_recon_drift_notified`: only notifies
        on the transition into that alert-worthy state, not every cycle
        it remains there.
        """
        current_symbols = {d["symbol"] for d in recon_report.symbol_drifts}
        by_symbol = {d["symbol"]: d for d in recon_report.symbol_drifts}

        for symbol in current_symbols:
            self._recon_drift_streak[symbol] = self._recon_drift_streak.get(symbol, 0) + 1

        # A symbol that cleared this cycle resets -- a fresh future drift
        # streak starts from zero, and it's no longer an alert-worthy state
        # (so it can notify again if it recurs later).
        for symbol in list(self._recon_drift_streak):
            if symbol not in current_symbols:
                del self._recon_drift_streak[symbol]
                self._recon_drift_notified.discard(symbol)

        for symbol in current_symbols:
            if self._recon_drift_streak[symbol] < RECON_DRIFT_ALERT_CYCLES:
                continue
            if symbol in self._recon_drift_notified:
                continue
            self._recon_drift_notified.add(symbol)
            await self._notify_target_weight_drift(by_symbol[symbol])

    async def _notify_target_weight_drift(self, drift: dict[str, Any]) -> None:
        """Best-effort push through vinu-agent's shared notify front door
        (routes_notify.py's /notify/reconciliation-drift -- reused with
        action="target_weight_drift" rather than a second route, same
        "shared infra, not N one-offs" reasoning already applied
        throughout this design series). A notification failure must
        never affect reconciliation itself."""
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/notify/reconciliation-drift",
                json={
                    "symbol": drift.get("symbol"),
                    "action": "target_weight_drift",
                    "expected_qty": drift.get("expected_qty"),
                    "actual_qty": drift.get("actual_qty"),
                    "drift_pct": drift.get("drift_pct"),
                },
            )
            if getattr(resp, "status_code", None) != 200:
                LOG.warning(
                    "Target-weight-drift notification for %s returned http %s",
                    drift.get("symbol"), getattr(resp, "status_code", "?"),
                )
        except Exception as e:  # noqa: BLE001
            LOG.warning(
                "Could not send target-weight-drift notification for %s: %s",
                drift.get("symbol"), e,
            )

    async def _fetch_live_decision_weights(self, cycle_id: str) -> list[dict[str, Any]]:
        """Point 7 option 1, plus the exit-mechanism fix (missing-pieces-
        of-system/new-theory-of-trading/system-wide-audit-and-design/
        04-synthesis-built-vs-missing-2026-09-28.md): converts unapplied
        live_decision EXECUTE records into a real, tracked open position
        (sized by each strategy's own `live_decision_position_size`
        config field -- see StrategyConfig's own docstring for why there
        is no invented default here), then re-emits a `target_weights`
        entry for EVERY currently open position, not just the one this
        cycle happened to newly apply.

        This second part is the actual bug fix: previously a decision was
        only ever folded into `target_weights` for the single cycle it
        was applied, then never again -- since SignalTranslator.translate()
        treats a symbol held but absent from `target_weights` as target
        0.0, the position was force-closed the very next cycle rather
        than genuinely held. Re-emitting the position's own stored size
        (not a fresh strategy-config fetch) is deliberate: it reflects
        what was actually opened, unaffected by a later config edit to
        `live_decision_position_size`.

        A decision is marked applied the moment it's converted into an
        open position (or confirmed unsized), whether or not it was
        actually sizeable -- an unsized (`live_decision_position_size ==
        0.0`) EXECUTE is real, final information (the strategy author
        hasn't wired sizing yet), not a transient failure, so it should
        not keep being re-logged every cycle forever, and has no position
        to open. A strategy-config fetch failure IS transient, so that
        record is left unapplied and retried next cycle instead.
        """
        pending = list_unapplied_executes(self._live_decision_backend)
        if pending:
            strategy_cache: dict[str, dict[str, Any] | None] = {}
            for record in pending:
                if record.strategy_id not in strategy_cache:
                    strategy_cache[record.strategy_id] = await self._fetch_strategy_config(record.strategy_id)
                strategy_cfg = strategy_cache[record.strategy_id]

                if strategy_cfg is None:
                    LOG.warning(
                        "[%s] Could not fetch strategy %s to size live-decision EXECUTE "
                        "on %s -- leaving unapplied, will retry next cycle",
                        cycle_id, record.strategy_id, record.ticker,
                    )
                    continue

                position_size = float(strategy_cfg.get("live_decision_position_size", 0.0) or 0.0)
                if position_size == 0.0:
                    LOG.warning(
                        "[%s] live-decision EXECUTE on %s/%s has no live_decision_position_size "
                        "configured -- not sized, no position opened for it",
                        cycle_id, record.ticker, record.strategy_id,
                    )
                else:
                    open_position(
                        self._live_decision_backend,
                        ticker=record.ticker, strategy_id=record.strategy_id,
                        position_size=position_size, opened_bar_ts=record.bar_ts,
                        trigger_id=record.trigger_id,
                    )
                    LOG.info(
                        "[%s] Opened live-decision position %s/%s at weight %.4f",
                        cycle_id, record.ticker, record.strategy_id, position_size,
                    )

                mark_decision_applied(self._live_decision_backend, record.id)

        weights: list[dict[str, Any]] = []
        for pos in list_open_positions(self._live_decision_backend):
            weights.append({
                "name": f"live_decision:{pos.strategy_id}",
                "symbol": pos.ticker,
                "target_weight": pos.position_size,
            })
        return weights

    async def _fetch_strategy_config(self, strategy_id: str) -> dict[str, Any] | None:
        try:
            resp = await self._http.get(
                f"{self._config.strategy_api_url}/strategy/strategies/{strategy_id}",
            )
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception as exc:
            LOG.warning("Could not fetch strategy %s: %s", strategy_id, exc)
            return None

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
