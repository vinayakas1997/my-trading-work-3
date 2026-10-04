from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel

from vinu_infra.auth import require_auth
from vinu_infra.runtime_settings import build_admin_settings_router
from vinu_infra.trade_audit_log import slippage_stats
from vinu_live.config import load_config
from vinu_live.feedback_loop import FeedbackLoopWorker
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    get_latest_snapshot,
    get_stage_state,
    list_snapshot_angle_names,
    list_snapshots,
    staleness_seconds,
)
from vinu_live.scheduler import LiveScheduler
from vinu_live.shadow_evaluator import ShadowEvaluator
from vinu_live.trade_plan.orchestrator import SETTINGS as TRADE_PLAN_SETTINGS
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator


class RebalanceRequestBody(BaseModel):
    symbol: str
    reason: str
    # how-to-make-it-live.md #23: a critical request bypasses the
    # orchestrator's 5% unrealized-gain protect for a genuinely urgent
    # reallocation.
    critical: bool = False


class EmergencyActionBody(BaseModel):
    # how-to-make-it-live.md #33: free-text note recorded with the halt /
    # resume for the audit trail.
    reason: str = "manual"


def create_app() -> FastAPI:
    app = FastAPI(title="vinu-live", version="0.1.0")

    router = APIRouter(prefix="/live")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "vinu-live"}

    @router.post("/cycle")
    async def trigger_cycle() -> dict[str, Any]:
        config = load_config()
        scheduler = LiveScheduler(config)
        try:
            return await scheduler.cycle()
        finally:
            await scheduler.close()

    @router.post("/trade-plan/cycle")
    async def trigger_trade_plan_cycle() -> dict[str, Any]:
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            return await orchestrator.cycle()
        finally:
            await orchestrator.close()

    @router.post("/feedback/cycle")
    async def trigger_feedback_cycle() -> dict[str, Any]:
        config = load_config()
        worker = FeedbackLoopWorker(config)
        try:
            return await worker.cycle()
        finally:
            await worker.close()

    @router.post("/shadow-evaluate")
    async def trigger_shadow_evaluate() -> dict[str, Any]:
        config = load_config()
        evaluator = ShadowEvaluator(
            research_api_url=config.research_api_url,
            agent_api_url=config.agent_api_url,
        )
        try:
            results = await evaluator.evaluate_all()
            return {"status": "ok", "n_artifacts": len(results), "results": results}
        finally:
            await evaluator.close()

    @router.post("/trade-plan/rebalance-request")
    async def submit_rebalance_request(body: RebalanceRequestBody) -> dict[str, Any]:
        """Phase 5's intake point (trade_plan/rebalance_intake.py), now
        HTTP-reachable -- the missing caller Phase 2's capital_allocator
        rebalancer (vinu-agent, a separate container) needed. Accepting a
        request here only means the symbol's own real next cycle will
        CONSIDER it as one more advisory input alongside its actual
        invalidation/contingency rules -- see
        TradePlanOrchestrator._evaluate_rebalance_request -- never that it
        will be honored. Constructing a fresh TradePlanOrchestrator per
        request (same as every other route here) is safe specifically
        because RebalanceRequestQueue is SQLite-backed at a shared,
        on-disk path under config.data_root -- the actual trade-plan-
        worker background process (same container, same volume, see
        entrypoint.sh) picks this request up on its own next cycle, not
        this throwaway instance."""
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            orchestrator.submit_rebalance_request(body.symbol, body.reason, critical=body.critical)
            return {"status": "ok", "symbol": body.symbol.upper()}
        finally:
            await orchestrator.close()

    @router.post("/trade-plan/emergency-flatten")
    async def emergency_flatten(body: EmergencyActionBody = EmergencyActionBody()) -> dict[str, Any]:
        """how-to-make-it-live.md #33: the panic switch. Sets the agent's
        global kill switch (blocks every new order, service-wide) AND submits a
        reduce_only market close for every open book position. Undo with
        /trade-plan/emergency-resume -- it is deliberately not automatic."""
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            return await orchestrator.emergency_flatten(reason=body.reason)
        finally:
            await orchestrator.close()

    @router.post("/trade-plan/emergency-resume")
    async def emergency_resume(body: EmergencyActionBody = EmergencyActionBody()) -> dict[str, Any]:
        """Lift the global kill switch. Does not reopen anything; normal cycles
        simply resume."""
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            return await orchestrator.emergency_resume(reason=body.reason)
        finally:
            await orchestrator.close()

    @router.get("/trade-plan/emergency-status")
    async def emergency_status() -> dict[str, Any]:
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            return await orchestrator.emergency_status()
        finally:
            await orchestrator.close()

    @router.get("/status")
    async def status() -> dict[str, str]:
        return {"status": "idle", "service": "vinu-live"}

    @router.get("/decision-context/{ticker}/{strategy_id}")
    async def decision_context(ticker: str, strategy_id: str) -> dict[str, Any]:
        """Point 5's read side (reverse-engineering/
        05-deciding-agent-and-precondition-tracking.md Part A) --
        vinu-agent's get_live_decision_context tool calls this to read
        the (ticker, strategy_id) pair's current stage + point 3's
        persisted live_snapshot, before composing it with
        get_signal_evidence's own historical lookup. A pair never seen
        by the poller yet is not an error -- same "idle" default
        get_stage_state itself returns, not a 404."""
        config = load_config()
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            state = get_stage_state(backend, ticker.upper(), strategy_id)
            novelty_row = get_latest_snapshot(backend, ticker.upper(), "live_novelty")
        finally:
            backend.close()
        return {
            "status": "ok",
            "novelty": novelty_row.snapshot_data if novelty_row else None,   # v2 B1/B2; None until the check has run
            "ticker": ticker.upper(),
            "strategy_id": strategy_id,
            "stage": state.stage,
            "trigger_id": state.trigger_id,
            "live_snapshot": state.last_snapshot,
            "last_checked_bar_ts": state.last_checked_bar_ts,
            "grace_window_expires_at": state.grace_window_expires_at,
        }

    @router.get("/decisions/needs-sizing")
    async def decisions_needs_sizing(limit: int = 100) -> dict[str, Any]:
        """EXECUTE decisions that never became a position because the strategy has no
        `live_decision_position_size` (v1 C2). Read-time anti-join, so it drains by
        itself once a size is configured and a later EXECUTE opens a position."""
        from vinu_live.live_decision.storage import list_needs_sizing

        config = load_config()
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            records = list_needs_sizing(backend, limit=limit)
        finally:
            backend.close()
        return {
            "status": "ok",
            "count": len(records),
            "hint": "set live_decision_position_size in the strategy YAML; later EXECUTEs will then open positions",
            "decisions": [
                {
                    "ticker": r.ticker, "strategy_id": r.strategy_id, "trigger_id": r.trigger_id,
                    "bar_ts": r.bar_ts, "recorded_at": r.recorded_at, "reasoning": r.reasoning,
                }
                for r in records
            ],
        }

    @router.get("/lockouts")
    async def lockouts() -> dict[str, Any]:
        """Symbols currently locked out of new entries by the per-symbol loss lockout (guards.symbol_lockout): streak,
        loss total, when it ends. Read-only. `enabled: false` means the lockout is off (VINU_LIVE_SYMBOL_LOCKOUT_LOSSES=0),
        in which case the list is empty by design. Built from the trade-plan book only (the scheduler writes no fills there)."""
        from vinu_live.book.positions import init_book
        from vinu_live.trade_plan import guards

        config = load_config()
        path = config.data_root / "trade_plan_book.db"
        enabled = guards.SYMBOL_LOCKOUT_LOSSES > 0 and guards.SYMBOL_LOCKOUT_HOURS > 0
        if not enabled or not path.exists():
            return {"enabled": enabled, "losses": guards.SYMBOL_LOCKOUT_LOSSES, "hours": guards.SYMBOL_LOCKOUT_HOURS, "count": 0, "lockouts": []}
        book = init_book(str(path))
        try:
            rows = guards.active_symbol_lockouts(book)
        finally:
            book.close()
        return {"enabled": True, "losses": guards.SYMBOL_LOCKOUT_LOSSES, "hours": guards.SYMBOL_LOCKOUT_HOURS, "count": len(rows), "lockouts": rows}

    @router.get("/executions")
    async def executions(limit: int = 100, symbol: str | None = None) -> dict[str, Any]:
        """The scheduler's order ledger (execution_log.py): every slice it tried to place or skipped, with the
        reference price it was sized at, the spread at decision time, the order type and the broker's
        submission answer, newest first, plus counts by outcome. Read-only. Records the SUBMISSION answer, not
        the fill price (an order is usually still working when the answer returns)."""
        from vinu_live.execution_log import ExecutionLog

        config = load_config()
        path = config.data_root / "execution_log.db"
        if not path.exists():
            return {"status": "none", "enabled": config.execution_log_enabled, "summary": {"total": 0}, "executions": []}
        log = ExecutionLog(path)
        try:
            rows = log.recent(limit=limit, symbol=symbol)
            summary = log.summary()
        finally:
            log.close()
        return {"status": "ok", "enabled": config.execution_log_enabled, "summary": summary, "count": len(rows), "executions": rows}

    @router.get("/decisions/{ticker}/{strategy_id}")
    async def decisions(ticker: str, strategy_id: str, limit: int = 20) -> dict[str, Any]:
        """The "accessing" half of the fix that closed the gap where
        live_decision_agent's real, evidence-grounded verdicts were only
        logged, never kept anywhere queryable (LiveDecisionRecord,
        live_decision/storage.py). Read-only, same posture as
        get_signal_evidence: honest raw rows, no computed statistic."""
        from vinu_live.live_decision.storage import list_closed_positions, list_live_decisions

        config = load_config()
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            records = list_live_decisions(backend, ticker.upper(), strategy_id, limit=limit)
            closed = list_closed_positions(backend, ticker.upper(), strategy_id, limit=limit)
        finally:
            backend.close()
        return {
            "status": "ok",
            "ticker": ticker.upper(),
            "strategy_id": strategy_id,
            "count": len(records),
            # What happened to earlier EXECUTEs: raw facts only, return is the reference return before costs.
            "closed_positions": [
                {
                    "opened_bar_ts": p.opened_bar_ts,
                    "closed_bar_ts": p.closed_bar_ts,
                    "closed_reason": p.closed_reason,
                    "entry_price": p.entry_price,
                    "exit_price": p.exit_price,
                    "return_pct": p.return_pct,
                }
                for p in closed
            ],
            "decisions": [
                {
                    "trigger_id": r.trigger_id,
                    "bar_ts": r.bar_ts,
                    "decision": r.decision,
                    "precondition_held": r.precondition_held,
                    "reasoning": r.reasoning,
                    "recorded_at": r.recorded_at,
                }
                for r in records
            ],
        }

    @router.get("/snapshots/{symbol}")
    async def snapshots(symbol: str) -> dict[str, Any]:
        """The read side of the present-data recording layer
        (missing-pieces-of-system/new-theory-of-trading/
        system-wide-audit-and-design/
        02-open-questions-strategy-and-simulation.md item #5): the latest
        recorded live snapshot for every angle_name this symbol has ever
        had one written for, mirroring `ticker_coverage.py`'s own "one
        column's worth of status per angle" pivot for historical data --
        `staleness_seconds` is computed fresh here, at read time, never
        stored (same rule that module already established)."""
        config = load_config()
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            angle_names = list_snapshot_angle_names(backend, symbol.upper())
            angles: dict[str, Any] = {}
            for name in angle_names:
                record = get_latest_snapshot(backend, symbol.upper(), name)
                if record is None:
                    continue
                angles[name] = {
                    "granularity": record.granularity,
                    "computed_at": record.computed_at,
                    "staleness_seconds": staleness_seconds(record.computed_at),
                    "snapshot_data": record.snapshot_data,
                }
        finally:
            backend.close()
        return {"status": "ok", "symbol": symbol.upper(), "angles": angles}

    @router.get("/snapshots/{symbol}/{angle_name}/history")
    async def snapshot_history(symbol: str, angle_name: str, limit: int = 50) -> dict[str, Any]:
        """History for one (symbol, angle_name) -- the present-data
        analogue of a historical run log, honest raw rows, no computed
        statistic beyond each row's own read-time staleness."""
        config = load_config()
        backend = LiveDecisionBackend(str(config.data_root / "live_decision.db"))
        try:
            records = list_snapshots(backend, symbol.upper(), angle_name, limit=limit)
        finally:
            backend.close()
        return {
            "status": "ok",
            "symbol": symbol.upper(),
            "angle_name": angle_name,
            "count": len(records),
            "snapshots": [
                {
                    "granularity": r.granularity,
                    "computed_at": r.computed_at,
                    "staleness_seconds": staleness_seconds(r.computed_at),
                    "snapshot_data": r.snapshot_data,
                }
                for r in records
            ],
        }

    @router.get("/tca/slippage")
    async def tca_slippage(symbol: str | None = None) -> dict[str, Any]:
        """TCA rollup over recorded entry-fill slippage -- the raw
        slippage_bps value was already computed and persisted per-trade by
        the orchestrator but nothing aggregated it past the pass/fail
        `slippage_exceeded` threshold. See the foundation-fixes audit in
        missing-pieces-of-system/narating-agents/."""
        return slippage_stats(symbol)

    # Live-tunable knobs (currently: the runtime correlation monitor's
    # threshold/reduce-pct/cooldown) -- GET/PATCH under /live/admin/settings,
    # gated by the same require_auth as everything else in this router. No
    # separate admin credential: whoever can call the trade-plan endpoints
    # can already submit/flatten orders, which is a strictly bigger power
    # than nudging a threshold.
    router.include_router(build_admin_settings_router(TRADE_PLAN_SETTINGS))

    app.include_router(router, dependencies=[Depends(require_auth)])
    return app
