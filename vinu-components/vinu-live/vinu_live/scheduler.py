from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import httpx

from vinu_infra.maturity_consultation import MaturityConsultationStore
from vinu_infra.pipeline_edge_recorder import record_edge
from vinu_live.book.positions import apply_fill, daily_realized_pnl, init_book
from vinu_live.breaker.engine import BreakerVerdict, check_limits
from vinu_live.breaker.limits import DEFAULT_LIMITS, BreakerLimits, BreakerState
from vinu_live.config import LiveConfig, load_config
from vinu_live.execution import compute_volume_profile, plan_twap, plan_vwap, schedule_slice_delays
from vinu_live.execution_log import ExecutionLog
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    list_needs_sizing,
    list_open_positions,
    list_unapplied_executes,
    mark_decision_applied,
    open_position,
    set_entry_price_if_missing,
)
from vinu_live.maturity_link import fetch_maturity_status, scale_limits_for_tier
from vinu_live.reconciliation import ReconciliationEngine
from vinu_live.signal_translator import SignalTranslator
from vinu_live.trade_plan.guards import (
    event_blackout_reason,
    extended_hours_route,
    fetch_quote_snapshot,
    halt_reason,
    instruction_increases_exposure,
    spread_gate_reason_from_bps,
    symbol_lockout_active,
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
    PRICE_MAX_AGE_HOURS,
    _choose_entry_order_type,
    _price_ts_age_hours,
    cooldown_active,
    turbulence_active,
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
        # Newest bar timestamp (UTC epoch s) per symbol, filled by
        # _fetch_prices -- only read by the opt-in entry guards below.
        self._last_price_ts: dict[str, float] = {}
        # True only when the last portfolio value came from a real broker equity read (logic-audit A6:
        # an equity-based daily P&L must never be built from a placeholder).
        self._equity_is_real = False
        # EXECUTEs the precondition gate refused in the most recent weights fetch (v1 A8); read by cycle().
        self._precondition_blocked: list[dict[str, Any]] = []
        # Order ledger (execution_log.py): log-only, never raises. None when disabled.
        self._execution_log: ExecutionLog | None = (
            ExecutionLog(self._config.data_root / "execution_log.db") if self._config.execution_log_enabled else None
        )
        self._current_cycle_id = ""
        # Broker health (loud failure reporting): reasons found during the current cycle, and how many
        # consecutive cycles had at least one.
        self._broker_problems: list[str] = []
        self._broker_down_streak = 0
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
        if self._execution_log is not None:
            self._execution_log.close()
        self._maturity_consultation_store.close()

    async def cycle(self) -> dict[str, Any]:
        """Execute one full trading cycle.

        Returns a dict with cycle results for logging/monitoring.
        """
        self._cycle_count += 1
        cycle_id = f"cycle_{self._cycle_count}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        LOG.info("[%s] Starting trading cycle", cycle_id)
        self._current_cycle_id = cycle_id
        self._broker_problems = []
        await self._enrich_execution_fills()

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
            if self._precondition_blocked:
                result["precondition_blocked"] = list(self._precondition_blocked)

            # v1 C2: an EXECUTE with no configured size is marked applied and
            # contributes no weight; surface how many are waiting on a size so
            # it is visible in the cycle result, not one log line.
            try:
                n_needs_sizing = len(list_needs_sizing(self._live_decision_backend))
                record_edge(
                    "live_decision.unsized_executes->live.api", "received" if n_needs_sizing else "empty",
                    f"{n_needs_sizing} EXECUTE(s) waiting on a configured size",
                )
                if n_needs_sizing:
                    result["needs_sizing"] = n_needs_sizing
            except Exception as e:  # noqa: BLE001 -- visibility only
                LOG.debug("needs-sizing count unavailable: %s", e)

            # A position closed outside this loop (a manual exit, a stop) must not stay in the book as committed money,
            # so this runs even when there is nothing to trade this cycle.
            try:
                from vinu_live.book.sync import sync_book_to_broker

                synced = sync_book_to_broker(self._book, await self._fetch_positions())
                if synced:
                    result["book_synced"] = synced
                    LOG.warning("[%s] Book cut down to what the broker holds: %s", cycle_id, synced)
            except Exception as e:  # noqa: BLE001 -- a sync problem must not stop the cycle
                LOG.warning("[%s] Book/broker sync failed: %s", cycle_id, e)

            if not target_weights:
                LOG.info("[%s] No target weights — skipping", cycle_id)
                result["status"] = "skipped_no_weights"
                return result

            current_positions = await self._fetch_positions()
            all_broker_positions = dict(current_positions)  # unfiltered: the breaker sees the whole account
            if self._config.scheduler_use_daily_allocation:
                result["allocation_source"] = portfolio.get("allocation_source", "state_fallback")
                if "deployable_fraction" in portfolio:
                    result["deployable_fraction"] = portfolio["deployable_fraction"]
            if self._config.scheduler_respect_trade_plan_symbols:
                target_weights, current_positions, ownership = await self._apply_symbol_ownership(
                    target_weights, current_positions,
                )
                if ownership:
                    result["ownership"] = ownership
            # A symbol the scheduler owns that nothing targets any more still needs a price, or the translator
            # skips it ("No usable price") and it is never closed.
            _orphans = (result.get("ownership") or {}).get("orphans_to_liquidate", [])
            prices = await self._fetch_prices(target_weights + [{"symbol": s} for s in _orphans])
            self._record_live_decision_entry_prices(prices)
            portfolio_value = await self._fetch_portfolio_value(current_positions, prices)

            instructions = self._translator.translate(
                target_weights, current_positions, portfolio_value, prices,
            )
            result["n_instructions"] = len(instructions)

            # logic-audit A4: opt-in entries-only guards (cooldown / stale data
            # / turbulence). Reducing instructions are never touched.
            instructions, guard_blocked = await self._apply_entry_guards(instructions)
            if guard_blocked:
                result["guard_blocked"] = guard_blocked
            blocked_symbols = {b["symbol"] for b in guard_blocked}

            # logic-audit A5: tag instructions that only shrink / close a position
            # so halts and gates below can leave them alone.
            if self._config.scheduler_exits_exempt_from_halts:
                for instr in instructions:
                    instr.reduces_exposure = not instruction_increases_exposure(
                        instr.side, instr.qty, instr.current_qty,
                    )

            if instructions:
                # item #24 finding #1: real risk-limit check (daily loss,
                # VaR, leverage, cluster exposure, position count) before
                # any order is planned/submitted -- this loop used to
                # never call this at all, unlike the orchestrator's own
                # entry/exit paths.
                if self._config.scheduler_breaker_uses_broker_account:
                    breaker_verdict, breaker_reason = await self._check_breaker(
                        portfolio_value, broker_positions=all_broker_positions,
                    )
                else:
                    breaker_verdict, breaker_reason = await self._check_breaker(portfolio_value)
                if breaker_verdict == BreakerVerdict.HALT:
                    LOG.warning(
                        "[%s] Breaker HALT -- skipping all order planning/execution this cycle: %s",
                        cycle_id, breaker_reason,
                    )
                    result["status"] = "halted_by_breaker"
                    result["breaker_reason"] = breaker_reason
                    exits = [i for i in instructions if i.reduces_exposure]
                    if self._config.scheduler_exits_exempt_from_halts and exits:
                        LOG.warning(
                            "[%s] Breaker HALT blocks new exposure only -- still executing %d "
                            "risk-reducing instruction(s)", cycle_id, len(exits),
                        )
                        exit_plan = await self._plan_execution(exits)
                        result["n_slices"] = exit_plan.total_orders
                        result["exits_only"] = True
                        result["submitted"] = await self._execute_plan(exit_plan, prices)
                else:
                    execution_plan = await self._plan_execution(instructions)
                    result["n_slices"] = execution_plan.total_orders

                    submitted = await self._execute_plan(execution_plan, prices)
                    result["submitted"] = submitted

            # A symbol an entry guard deliberately held back is a decision, not
            # drift -- exclude it so reconciliation does not alert on it.
            expected_positions = self._compute_expected_positions(
                [tw for tw in target_weights if tw.get("symbol") not in blocked_symbols],
                prices, portfolio_value,
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

        await self._finish_broker_health(cycle_id, result)
        return result

    async def _enrich_execution_fills(self) -> None:
        """Ask the broker how the recently accepted orders ended up and write fill price / quantity / status and the
        slippage into the ledger. Read-only toward the broker, bounded by `execution_fill_enrichment_batch`, and
        best-effort: any failure (including the agent API being down) is swallowed and the same rows are retried
        next cycle. Never changes an order."""
        if self._execution_log is None or not self._config.execution_fill_enrichment_enabled:
            return
        try:
            rows = self._execution_log.unresolved_orders(limit=self._config.execution_fill_enrichment_batch)
            for row in rows:
                try:
                    resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/order/{row['order_id']}")
                    if getattr(resp, "status_code", None) != 200:
                        continue
                    body = resp.json()
                    if not isinstance(body, dict) or body.get("status") != "ok":
                        continue
                    self._execution_log.record_fill(
                        row["id"], fill_status=body.get("order_status"),
                        fill_price=body.get("filled_avg_price"), filled_qty=body.get("filled_qty"),
                    )
                    self._write_fill_to_book(row, body.get("filled_qty"), body.get("filled_avg_price"))
                except Exception as e:  # noqa: BLE001 -- one order's lookup must not stop the others
                    LOG.debug("fill lookup failed for order %s: %s", row.get("order_id"), e)
        except Exception as e:  # noqa: BLE001
            LOG.debug("fill enrichment failed: %s", e)

    def _write_fill_to_book(self, row: dict[str, Any], filled_qty: Any, fill_price: Any) -> None:
        """Put what the broker filled into the trade-plan book, so the breaker, cooldown and symbol lockout see the
        scheduler's own trades (they read only the book). Only the part of the fill not yet written is applied, so a
        partial fill that grows is counted once. Never raises: a book problem must not stop the cycle, but it is
        recorded on the edge `book.writes->live.scheduler`."""
        edge = "book.writes->live.scheduler"
        try:
            qty, price = float(filled_qty or 0), float(fill_price or 0)
            new = qty - float(row.get("book_applied_qty") or 0)
            if new <= 1e-9 or price <= 0:
                return
            outcome = apply_fill(self._book, str(row["symbol"]), str(row["side"]), new, price)
            if outcome in ("opened", "added", "reduced", "closed"):
                self._execution_log.mark_book_applied(row["id"], qty)
                record_edge(edge, "received", f"{row['side']} {new:g} {row['symbol']} -> {outcome}")
            else:
                record_edge(edge, "missing", f"{row['side']} {new:g} {row['symbol']}: not written ({outcome})")
        except Exception as e:  # noqa: BLE001
            LOG.warning("could not write the fill of %s %s to the book: %s", row.get("side"), row.get("symbol"), e)
            record_edge(edge, "missing", f"{row.get('symbol')}: {e}")

    async def _finish_broker_health(self, cycle_id: str, result: dict[str, Any]) -> None:
        """Loud failure reporting for the broker. Called once at the end of every cycle that reached the broker
        reads; never raises and never changes what the cycle did."""
        try:
            problems = list(dict.fromkeys(self._broker_problems))  # de-duplicated, order kept
            if problems:
                self._broker_down_streak += 1
                result["broker_unreachable"] = problems
                LOG.error(
                    "[%s] BROKER PROBLEM (%d consecutive cycle(s)): %s", cycle_id, self._broker_down_streak, "; ".join(problems),
                )
                every = max(1, int(self._config.broker_unreachable_renotify_cycles))
                if self._broker_down_streak == 1 or self._broker_down_streak % every == 0:
                    await self._notify_broker_health(
                        "broker_unreachable",
                        f"{'; '.join(problems)} (cycle {cycle_id}, {self._broker_down_streak} consecutive bad cycle(s))",
                    )
            elif self._broker_down_streak > 0:
                await self._notify_broker_health(
                    "broker_recovered", f"reachable again after {self._broker_down_streak} bad cycle(s)",
                )
                LOG.warning("[%s] Broker reachable again after %d bad cycle(s)", cycle_id, self._broker_down_streak)
                self._broker_down_streak = 0
        except Exception as e:  # noqa: BLE001 -- health reporting must never break a cycle
            LOG.debug("broker health reporting failed: %s", e)

    async def _notify_broker_health(self, action: str, detail: str) -> None:
        """Best-effort push through the shared notify front door (the same route the drift and stuck-decision alerts use).
        Goes through the agent API, so if the AGENT API itself is down this cannot be delivered: the ERROR log above is
        then the only trace."""
        if not self._config.broker_unreachable_notify_enabled:
            return
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/notify/reconciliation-drift",
                json={"symbol": "BROKER", "action": action, "detail": detail},
            )
            resp.raise_for_status()
        except Exception as e:  # noqa: BLE001
            LOG.warning("could not send the %s notification: %s", action, e)

    def _record_live_decision_entry_prices(self, prices: dict[str, float]) -> None:
        """logic-audit A3: stamp the price this cycle sizes at onto any open
        live-decision position that has no entry reference yet (first priced
        cycle after it opened), so the poller's rule-based stop has something
        to measure against. Best-effort and write-once; never affects orders.
        An approximation of the fill price (the last daily close the order is
        sized on), documented as such."""
        try:
            stamped = 0
            for pos in list_open_positions(self._live_decision_backend):
                if pos.entry_price is None and prices.get(pos.ticker):
                    set_entry_price_if_missing(
                        self._live_decision_backend, pos.id, prices[pos.ticker],
                    )
                    stamped += 1
            record_edge(
                "live_decision.entry_price<-live.scheduler", "received" if stamped else "empty",
                f"stamped {stamped} position(s)",
            )
        except Exception as e:  # noqa: BLE001 -- never let this touch order flow
            LOG.warning("Could not record live-decision entry prices: %s", e)
            record_edge("live_decision.entry_price<-live.scheduler", "missing", f"write failed: {e}")

    async def _apply_entry_guards(
        self, instructions: list[Any],
    ) -> tuple[list[Any], list[dict[str, Any]]]:
        """(kept instructions, blocked records). Off unless
        `scheduler_entry_guards_enabled`; then drops only instructions that
        INCREASE exposure when (1) the consecutive-loss cooldown is active,
        (2) the symbol's newest price bar is older than PRICE_MAX_AGE_HOURS,
        or (3) its 14-day realized vol trips the turbulence pause -- the same
        three guards, thresholds and fail-open posture the trade-plan
        orchestrator applies to its entries. Anything that reduces or closes
        a position always passes. Any error in here fails open (instructions
        returned untouched) so a guard bug can never stop an order.

        The cooldown and the symbol lockout read the book's closed positions, and this path writes its own fills there
        (`_write_fill_to_book`), so they see this path's losses too. A position the book is cut back to match the broker
        (book/sync.py) closes at zero P&L and is not counted as a loss."""
        if not self._config.scheduler_entry_guards_enabled or not instructions:
            return instructions, []
        try:
            locked, lock_reason = cooldown_active(self._book)
            record_edge("guard.cooldown->live.scheduler", "received", "locked" if locked else "not locked")
            kept: list[Any] = []
            blocked: list[dict[str, Any]] = []
            for instr in instructions:
                if not instruction_increases_exposure(instr.side, instr.qty, instr.current_qty):
                    kept.append(instr)
                    continue
                guard, reason = "", ""
                if locked:
                    guard, reason = "cooldown", lock_reason
                if not guard:
                    sym_locked, sym_reason = symbol_lockout_active(self._book, instr.symbol)
                    if sym_locked:
                        guard, reason = "symbol_lockout", sym_reason
                if not guard and PRICE_MAX_AGE_HOURS > 0:
                    age = _price_ts_age_hours(self._last_price_ts.get(instr.symbol))
                    record_edge(
                        "guard.data_freshness->live.scheduler", "received" if age is not None else "missing",
                        f"{instr.symbol}: " + (f"newest bar {age:.1f}h old" if age is not None else "no bar timestamp recorded"),
                    )
                    if age is not None and age > PRICE_MAX_AGE_HOURS:
                        guard = "stale_data"
                        reason = f"price data age {age:.1f}h exceeds max {PRICE_MAX_AGE_HOURS:.1f}h"
                if not guard:
                    turb, turb_reason = await turbulence_active(self._fetch_recent_closes, instr.symbol)
                    if turb:
                        guard, reason = "turbulence", turb_reason
                if guard:
                    LOG.warning(
                        "Entry guard %s -- holding back %s %s %s: %s",
                        guard, instr.side, instr.qty, instr.symbol, reason,
                    )
                    blocked.append({
                        "symbol": instr.symbol, "side": instr.side, "qty": instr.qty,
                        "guard": guard, "reason": reason,
                    })
                else:
                    kept.append(instr)
            return kept, blocked
        except Exception as e:  # noqa: BLE001 -- a guard bug must never stop an order
            LOG.warning("Entry guards failed, failing open (instructions untouched): %s", e)
            return instructions, []

    async def _fetch_recent_closes(self, symbol: str) -> list[float]:
        """Daily closes for the turbulence check; [] on any problem (the guard
        then fails open, same as the orchestrator's)."""
        try:
            resp = await self._http.get(
                f"{self._config.stock_price_api_url}/stock/candles/{symbol}",
                params={"interval": "1d", "days": 30, "adjusted": True},
            )
            if resp.status_code == 200:
                bars = resp.json().get("data", [])
                closes = [float(b["close"]) for b in bars if b.get("close")]
                record_edge(
                    "guard.turbulence->live.scheduler", "received" if closes else "missing",
                    f"{symbol}: {len(closes)} daily close(s)",
                )
                return closes
            record_edge("guard.turbulence->live.scheduler", "missing", f"{symbol}: HTTP {resp.status_code}")
        except Exception as e:  # noqa: BLE001
            LOG.debug("Could not fetch recent closes for %s: %s", symbol, e)
            record_edge("guard.turbulence->live.scheduler", "missing", f"{symbol}: {e}")
        return []

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
        record_edge(
            "maturity.status->live.limits", "missing" if status is None else "received",
            "fetch_maturity_status returned None" if status is None else "",
            payload=status,
        )
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

    def _account_daily_pnl(self, equity: float) -> float | None:
        """logic-audit A6: today's P&L from the account itself -- `equity` minus the first equity this
        scheduler saw on the current UTC day (persisted in `breaker_day_equity.json` so a restart keeps it).
        The first sighting of a day returns 0.0. Includes unrealized moves. None on any problem (the
        caller then keeps the book's realized figure). Limit: the baseline is the first equity this
        process saw today, not the market-open or prior-close equity."""
        try:
            path = self._config.data_root / "breaker_day_equity.json"
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            baseline = None
            if path.exists():
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved.get("date") == today and saved.get("equity") is not None:
                    baseline = float(saved["equity"])
            if baseline is None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"date": today, "equity": float(equity)}), encoding="utf-8")
                return 0.0
            return float(equity) - baseline
        except Exception as e:  # noqa: BLE001 -- must never stop the breaker
            LOG.warning("Could not compute account-based daily P&L, using realized book P&L: %s", e)
            return None

    async def _check_breaker(
        self, portfolio_value: float, broker_positions: dict[str, float] | None = None,
    ) -> tuple[str, str | None]:
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

        from vinu_infra.account_mode import real_capital

        positions = list_open_positions(self._book)
        extra: dict[str, Any] = {}
        daily_pnl = daily_realized_pnl(self._book)
        # With a real-money base the limits are percentages of THAT money: 5 percent of the 96,000 paper balance is
        # 4,800 dollars, which a 20-dollar account can never lose. The system's own positions (the book) are what count,
        # not whatever else the paper account holds.
        capital_base = real_capital()
        if capital_base is not None:
            portfolio_value = capital_base
            extra["positions"] = [p for p in positions if p.side == "long"]
        elif self._config.scheduler_breaker_uses_broker_account:
            # logic-audit A6: the account the scheduler actually trades, not the plan book.
            if broker_positions is not None:
                positions = [
                    SimpleNamespace(symbol=s, qty=abs(q), side="long" if q > 0 else "short")
                    for s, q in broker_positions.items() if abs(q) >= 0.001
                ]
                extra["positions"] = positions
            if self._equity_is_real:
                account_pnl = self._account_daily_pnl(portfolio_value)
                if account_pnl is not None:
                    daily_pnl = account_pnl
        symbols = sorted({p.symbol for p in positions})
        prices = await self._fetch_prices([{"symbol": s} for s in symbols]) if symbols else {}
        if capital_base is not None:
            # today's loss on the base: realized today plus what the open positions are down since entry (a
            # conservative stand-in for the day's move on positions held longer than a day)
            daily_pnl += sum((prices[p.symbol] - p.avg_entry) * p.qty for p in extra["positions"] if prices.get(p.symbol))
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
            **extra,
        )
        record_edge("breaker.limits->live.scheduler", "received", f"verdict={verdict}")
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
                f"{self._config.agent_api_url}/agent/notify/reconciliation-drift",
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
                record_edge("reconciliation_drift->agent.notify", "missing", f"{drift.get('symbol')}: HTTP {getattr(resp, 'status_code', '?')}")
            else:
                record_edge("reconciliation_drift->agent.notify", "received", f"{drift.get('symbol')}")
        except Exception as e:  # noqa: BLE001
            LOG.warning(
                "Could not send target-weight-drift notification for %s: %s",
                drift.get("symbol"), e,
            )
            record_edge("reconciliation_drift->agent.notify", "missing", f"{drift.get('symbol')}: {e}")

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
        self._precondition_blocked = []
        if pending:
            strategy_cache: dict[str, dict[str, Any] | None] = {}
            for record in pending:
                record_edge(
                    "precondition_held->live.scheduler", "received" if record.precondition_held is not None else "missing",
                    f"{record.ticker}/{record.strategy_id}: precondition_held={record.precondition_held}",
                )
                if self._config.precondition_enforcing_enabled and record.precondition_held is False:
                    # v1 A8: the strategy's own precondition did not hold -- no position. Final, so mark applied.
                    LOG.warning(
                        "[%s] live-decision EXECUTE on %s/%s refused: precondition_held is False "
                        "(precondition_enforcing_enabled)", cycle_id, record.ticker, record.strategy_id,
                    )
                    self._precondition_blocked.append({
                        "ticker": record.ticker, "strategy_id": record.strategy_id,
                        "decision_id": record.id, "bar_ts": record.bar_ts,
                    })
                    mark_decision_applied(self._live_decision_backend, record.id)
                    continue
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
        record_edge("live_decision.executes->live.scheduler", "received" if weights or pending else "empty")
        return weights

    async def _fetch_strategy_config(self, strategy_id: str) -> dict[str, Any] | None:
        try:
            resp = await self._http.get(
                f"{self._config.strategy_api_url}/strategy/strategies/{strategy_id}",
            )
            if resp.status_code != 200:
                record_edge("strategy.config->live.scheduler", "missing", f"strategy {strategy_id}: HTTP {resp.status_code}")
                return None
            body = resp.json()
            record_edge("strategy.config->live.scheduler", "received", payload=body)
            return body
        except Exception as exc:
            LOG.warning("Could not fetch strategy %s: %s", strategy_id, exc)
            record_edge("strategy.config->live.scheduler", "missing", f"strategy {strategy_id}: {exc}")
            return None

    async def _fetch_portfolio(self) -> dict[str, Any]:
        if self._config.scheduler_use_daily_allocation:
            allocation = await self._fetch_daily_allocation()
            if allocation is not None:
                return allocation
        edge = "portfolio.state->live.scheduler"
        try:
            resp = await self._http.get(f"{self._config.portfolio_api_url}/portfolio/state")
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            record_edge(edge, "missing", f"GET /portfolio/state failed: {e}")
            raise  # unchanged: a failed portfolio read aborts the cycle
        empty = not isinstance(data, dict) or data.get("status") == "empty" or not data.get("weights")
        record_edge(edge, "empty" if empty else "received", payload=data)
        return data

    async def _fetch_daily_allocation(self) -> dict[str, Any] | None:
        """logic-audit A1: the portfolio's tilted, capital-scaled allocation, shaped like
        /portfolio/state so the rest of the cycle is unchanged. Each weight is multiplied by
        `deployable_equity / account_equity` (clamped to [0, 1]; 1.0 when either is missing) --
        the drawdown ladder, maturity ladder and reserve act on TOTAL capital, not on the
        relative weights, so this is where they finally bound real orders. None on any failure
        (the caller then reads /portfolio/state, today's behavior, and `allocation_source`
        says which one was used)."""
        edge = "portfolio.daily_allocation->live.scheduler"
        try:
            resp = await self._http.get(f"{self._config.portfolio_api_url}/portfolio/daily-allocation")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, dict):
                raise ValueError(f"unexpected daily-allocation shape: {type(data).__name__}")
        except Exception as e:  # noqa: BLE001 -- fall back to /portfolio/state
            LOG.warning("daily-allocation unavailable, falling back to /portfolio/state: %s", e)
            record_edge(edge, "missing", f"GET /portfolio/daily-allocation failed: {e}")
            return None
        weights = data.get("weights")
        if data.get("status") != "ok" or not weights:
            record_edge(edge, "empty")
            return {**data, "weights": [], "allocation_source": "daily_allocation"}
        fraction = 1.0
        try:
            equity, deployable = data.get("account_equity"), data.get("deployable_equity")
            if equity is not None and deployable is not None and float(equity) > 0:
                fraction = min(1.0, max(0.0, float(deployable) / float(equity)))
        except (TypeError, ValueError):
            fraction = 1.0
        scaled = [{**w, "target_weight": float(w.get("target_weight", 0.0)) * fraction} for w in weights]
        record_edge(edge, "received", payload=data)
        return {**data, "weights": scaled, "allocation_source": "daily_allocation", "deployable_fraction": fraction}

    async def _fetch_trade_plan_symbols(self) -> set[str] | None:
        """Symbols of ACTIVE trade_plan artifacts (upper-case), or None when they cannot be read."""
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/artifacts",
                params={"status": "ACTIVE", "type_": "trade_plan"},
            )
            if resp.status_code != 200:
                return None
            symbols: set[str] = set()
            for summary in resp.json():
                artifact_id = summary.get("artifact_id")
                if not artifact_id:
                    continue
                detail = await self._http.get(f"{self._config.research_api_url}/research/trade-plan/{artifact_id}")
                if detail.status_code != 200:
                    return None  # an unreadable plan means ownership is not fully known
                raw = detail.json().get("trade_plan_data")
                plan = json.loads(raw) if isinstance(raw, str) else (raw or {})
                sym = str(plan.get("symbol") or "").upper()
                if sym:
                    symbols.add(sym)
            return symbols
        except Exception as e:  # noqa: BLE001
            LOG.warning("Could not read active trade plans for symbol ownership: %s", e)
            return None

    async def _apply_symbol_ownership(
        self, target_weights: list[dict[str, Any]], current_positions: dict[str, float],
    ) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
        """logic-audit A2 (opt-in): who may this path trade? Three kinds of symbol:

        * orchestrator-owned (open position in the trade-plan book, or an ACTIVE trade_plan artifact): removed
          from both the targets and the positions the translator sees -- never sized, never closed here.
        * scheduler-owned and no longer targeted (the order ledger shows the scheduler had a BUY accepted for
          it, or it is listed in `scheduler_adopted_symbols`): kept, so the translator closes it (a retired
          strategy's symbol). They are returned as `orphans_to_liquidate` so the cycle can fetch their
          prices -- a symbol with no price is silently skipped, which is why nothing was ever closed before.
        * anything else held with no target (a position placed by hand, or by something this path cannot
          identify): left alone.
        When the active-plan read fails ownership is unknown, so every held position with no target is left
        alone. Never raises: a failure here leaves the inputs untouched."""
        info: dict[str, Any] = {}
        try:
            from vinu_live.book.positions import list_open_positions as _book_open_positions

            book_symbols = {p.symbol.upper() for p in _book_open_positions(self._book)}
            plan_symbols = await self._fetch_trade_plan_symbols()
            targeted = {str(tw.get("symbol", "")).upper() for tw in target_weights}
            scheduler_owned = {
                s.strip().upper() for s in (self._config.scheduler_adopted_symbols or "").split(",") if s.strip()
            }
            if self._execution_log is not None:
                try:
                    scheduler_owned |= self._execution_log.bought_symbols()
                except Exception as e:  # noqa: BLE001 -- unknown ownership means "leave alone"
                    LOG.warning("Could not read the order ledger for scheduler ownership: %s", e)
            # The scheduler writes its own fills into the book, so a book position is not proof that the
            # trade-plan orchestrator owns it: a symbol the scheduler bought (and no active plan claims) stays the
            # scheduler's, otherwise it could never be resized or closed after its first fill.
            owned = (book_symbols - (scheduler_owned - (plan_symbols or set()))) | (plan_symbols or set())
            held_untargeted = {s for s in current_positions if s.upper() not in targeted and s.upper() not in owned}
            if plan_symbols is None:
                held_unowned_unknown = held_untargeted
                orphans: set[str] = set()
            else:
                orphans = {s for s in held_untargeted if s.upper() in scheduler_owned}
                held_unowned_unknown = held_untargeted - orphans
            if orphans:
                info["orphans_to_liquidate"] = sorted(orphans)
            skipped_targets = sorted({str(tw.get("symbol", "")).upper() for tw in target_weights} & owned)
            left_alone = sorted({s for s in current_positions if s.upper() in owned} | held_unowned_unknown)
            if skipped_targets:
                target_weights = [tw for tw in target_weights if str(tw.get("symbol", "")).upper() not in owned]
            current_positions = {s: q for s, q in current_positions.items() if s not in left_alone}
            if skipped_targets:
                info["targets_skipped_orchestrator_owned"] = skipped_targets
            if left_alone:
                info["positions_left_alone"] = left_alone
                LOG.warning("Symbol ownership: leaving %s alone (orchestrator-owned, hand-placed or ownership unknown)", left_alone)
            if plan_symbols is None:
                info["ownership_unknown"] = True
        except Exception as e:  # noqa: BLE001 -- must never stop the cycle
            LOG.warning("Symbol ownership check failed, inputs untouched: %s", e)
        return target_weights, current_positions, info

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
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/positions")
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                raise ValueError(
                    f"Unexpected /agent/broker/positions response shape: {type(data).__name__}"
                )
        except Exception as e:
            self._broker_problems.append(f"broker positions could not be read ({type(e).__name__}: {e})")
            raise
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
                        try:
                            self._last_price_ts[symbol] = float(bars[-1]["bar_ts"])
                        except (KeyError, TypeError, ValueError):
                            # no usable timestamp -> drop any old one so the
                            # freshness guard fails open instead of blocking
                            # on a lingering stale value.
                            self._last_price_ts.pop(symbol, None)
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
        self._equity_is_real = False
        read_failed = True  # only an explicit `configured: false` reply clears this
        try:
            resp = await self._http.get(f"{self._config.agent_api_url}/agent/broker/account")
            if resp.status_code == 200:
                account = resp.json()
                if account.get("configured") and account.get("equity") is not None:
                    self._equity_is_real = True
                    return float(account["equity"])
                read_failed = bool(account.get("configured"))
            else:
                LOG.warning("Account equity read returned HTTP %s", resp.status_code)
        except Exception as e:
            LOG.warning("Could not fetch account equity: %s", e)

        if read_failed:
            self._broker_problems.append("a configured broker's account equity could not be read")
        if read_failed and self._config.abort_on_equity_read_failure:
            # logic-audit A7: a broker that IS configured but could not be read
            # must not be sized from a placeholder or from positions alone.
            raise RuntimeError(
                "broker account equity could not be read; aborting the cycle "
                "rather than sizing on a placeholder (abort_on_equity_read_failure)"
            )

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

    @staticmethod
    def _order_outcome(resp: Any) -> tuple[str, dict[str, Any]]:
        """(outcome, ledger details) for the agent API's answer to POST /agent/broker/order.

        The route answers HTTP 200 even when OrderGuard refuses the order or the broker call fails: the real
        verdict is the JSON `status` (`submitted` / `rejected` / `pending_confirmation` / `error`). This path used
        to call every HTTP < 400 answer "submitted" without reading the body (the orchestrator does read it), so a
        refused order was reported as placed. An unreadable or unrecognised body still counts as submitted (the
        old behavior); only an explicit refusal is reported as one."""
        http = getattr(resp, "status_code", 0)
        if not isinstance(http, int) or http >= 400:
            return "failed", {}
        try:
            body = resp.json()
        except Exception:  # noqa: BLE001
            body = None
        if not isinstance(body, dict):
            return "submitted", {}
        status = body.get("status")
        if status in ("rejected", "pending_confirmation", "error"):
            reason = body.get("reason") or body.get("message") or body.get("error") or ""
            code = body.get("reason_code")
            return str(status), {"reason": f"{reason} [{code}]" if code else str(reason)}
        detail: dict[str, Any] = {}
        if body.get("order_id"):
            detail["order_id"] = str(body["order_id"])
        if body.get("broker_status"):
            detail["broker_status"] = str(body["broker_status"])
        return "submitted", detail

    def _log_execution(self, slice_: Any, **fields: Any) -> None:
        """One ledger row for this slice. Never raises (the ledger itself swallows errors too)."""
        if self._execution_log is None:
            return
        try:
            self._execution_log.record(
                cycle_id=self._current_cycle_id, symbol=slice_.symbol, side=slice_.side, qty=slice_.qty,
                slice_number=slice_.slice_number, total_slices=slice_.total_slices, **fields,
            )
        except Exception as e:  # noqa: BLE001
            LOG.debug("execution ledger row failed: %s", e)

    async def _execute_plan(self, plan: Any, prices: dict[str, float] | None = None) -> list[dict]:
        # Checks both the local HALT file AND the agent's cross-process kill
        # switch (see guards.halt_reason's docstring) -- this path used to
        # only check the local file, so a breaker/OOD-engaged remote halt
        # left the TWAP/VWAP loop cycling and failing orders instead of
        # stopping cleanly.
        _halt = await halt_reason(self._http, self._config.agent_api_url, edge_id="halt_flag->live.scheduler")
        exempt = self._config.scheduler_exits_exempt_from_halts  # logic-audit A5
        slices = list(plan.slices)
        if _halt:
            if exempt:
                slices = [s for s in slices if s.reduce_only]
            if not exempt or not slices:
                LOG.warning("Trading halted (%s) — skipping all order execution", _halt)
                return []
            LOG.warning(
                "Trading halted (%s) -- executing only the %d risk-reducing slice(s)", _halt, len(slices),
            )
        prices = prices or {}
        submitted = []
        delays = schedule_slice_delays(
            len(slices), total_window_minutes=60,
        )
        import time as _time

        for i, slice_ in enumerate(slices):
            exit_slice = exempt and slice_.reduce_only
            if exempt and _halt and not slice_.reduce_only:
                continue  # a halt that appeared mid-plan: drop the increases, keep the exits
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
            _spread_bps, _quote_mid = await fetch_quote_snapshot(self._http, self._config.stock_price_api_url, slice_.symbol)
            # A per-instruction max_slippage_pct budget (SignalTranslator's
            # own knob, previously set but never read by anything -- see
            # OrderInstruction.max_slippage_pct's docstring) tightens the
            # ceiling below the global default when it's the stricter of
            # the two; it never loosens it.
            _spread_ceiling = MAX_SPREAD_BPS
            if slice_.max_slippage_pct > 0:
                _spread_ceiling = min(MAX_SPREAD_BPS, slice_.max_slippage_pct * 10_000.0)
            # A5: a risk-reducing slice is never held back by the spread/event gate.
            _block_reason = None if exit_slice else (
                spread_gate_reason_from_bps(_spread_bps, _spread_ceiling) or await event_blackout_reason(
                    self._http, self._config.stock_price_api_url, slice_.symbol, EVENT_BLACKOUT_HOURS,
                )
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
                self._log_execution(
                    slice_, outcome="skipped", reference_price=prices.get(slice_.symbol), spread_bps=_spread_bps,
                    quote_mid=_quote_mid, reduce_only=exit_slice, reason=str(_block_reason),
                )
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
            # A5: an exit goes as a market order -- a passive limit could rest unfilled and trap the position.
            _order_type = "market" if exit_slice else _choose_entry_order_type(_spread_bps, _slippage_budget)
            _limit_price: float | None = None
            if _order_type == "limit":
                _price = prices.get(slice_.symbol)
                if _price is not None and _price > 0:
                    _offset = PASSIVE_LIMIT_OFFSET_BPS / 10_000.0
                    _limit_price = _price * (1 - _offset) if slice_.side == "buy" else _price * (1 + _offset)
                else:
                    _order_type = "market"
            # Pre-market, after-hours and overnight take only limit orders: an exit or a market entry becomes a limit
            # set a little through the quote (the order guard refuses a market order there, which would trap exits).
            _order_type, _limit_price, _ = await extended_hours_route(
                self._http, self._config.stock_price_api_url, slice_.symbol, slice_.side, _order_type, _limit_price,
                reference_price=prices.get(slice_.symbol),
            )

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
                if exit_slice:
                    _payload["reduce_only"] = True
                resp = await self._http.post(
                    f"{self._config.agent_api_url}/agent/broker/order",
                    json=_payload,
                )
                outcome, detail = self._order_outcome(resp)
                if exit_slice:
                    record_edge(
                        "order.reduce_only->live.scheduler", "received" if outcome == "submitted" else "missing",
                        f"{slice_.symbol}: reduce-only {slice_.side} -> {outcome}",
                    )
                result = {
                    "symbol": slice_.symbol,
                    "side": slice_.side,
                    "qty": slice_.qty,
                    "slice": slice_.slice_number,
                    "status": outcome,
                }
                if outcome not in ("submitted", "failed") and detail.get("reason"):
                    result["reason"] = detail["reason"]
                if outcome in ("failed", "error"):
                    self._broker_problems.append(f"order for {slice_.symbol} failed at the broker/API level ({outcome})")
                submitted.append(result)
                self._log_execution(
                    slice_, outcome=outcome, reference_price=prices.get(slice_.symbol), spread_bps=_spread_bps,
                    quote_mid=_quote_mid, order_type=_order_type, limit_price=_limit_price, reduce_only=exit_slice,
                    client_order_id=_cid, http_status=resp.status_code, **detail,
                )
                if outcome == "submitted":
                    LOG.info(
                        "Submitted %s %s %s (slice %d/%d)",
                        slice_.side, slice_.qty, slice_.symbol,
                        slice_.slice_number, slice_.total_slices,
                    )
                else:
                    LOG.warning(
                        "Order for %s %s %s was NOT accepted (%s): %s",
                        slice_.side, slice_.qty, slice_.symbol, outcome, detail.get("reason", ""),
                    )
            except Exception as e:
                LOG.warning("Order submission failed: %s", e)
                self._broker_problems.append(f"order for {slice_.symbol} could not be sent ({type(e).__name__})")
                submitted.append({
                    "symbol": slice_.symbol,
                    "side": slice_.side,
                    "qty": slice_.qty,
                    "slice": slice_.slice_number,
                    "status": "error",
                    "error": str(e),
                })
                self._log_execution(
                    slice_, outcome="error", reference_price=prices.get(slice_.symbol), spread_bps=_spread_bps,
                    quote_mid=_quote_mid, order_type=_order_type, limit_price=_limit_price, reduce_only=exit_slice,
                    client_order_id=_cid, reason=str(e),
                )

            if i < len(delays):
                await asyncio.sleep(delays[i])
                _mid_halt = await halt_reason(self._http, self._config.agent_api_url, edge_id="halt_flag->live.scheduler")
                if _mid_halt:
                    if exempt:
                        _halt = _mid_halt  # remaining increases are dropped above; exits still go
                        continue
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
