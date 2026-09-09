from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel

from vinu_infra.auth import require_auth
from vinu_live.config import load_config
from vinu_live.feedback_loop import FeedbackLoopWorker
from vinu_live.scheduler import LiveScheduler
from vinu_live.shadow_evaluator import ShadowEvaluator
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

    app.include_router(router, dependencies=[Depends(require_auth)])
    return app
