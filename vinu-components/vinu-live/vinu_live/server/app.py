from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI

from vinu_live.config import load_config
from vinu_live.feedback_loop import FeedbackLoopWorker
from vinu_live.scheduler import LiveScheduler
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator


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

    @router.get("/status")
    async def status() -> dict[str, str]:
        return {"status": "idle", "service": "vinu-live"}

    app.include_router(router)
    return app
