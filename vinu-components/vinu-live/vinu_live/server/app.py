from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from vinu_live.config import load_config
from vinu_live.feedback_loop import FeedbackLoopWorker
from vinu_live.scheduler import LiveScheduler
from vinu_live.trade_plan.orchestrator import TradePlanOrchestrator


def create_app() -> FastAPI:
    app = FastAPI(title="vinu-live", version="0.1.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "vinu-live"}

    @app.post("/cycle")
    async def trigger_cycle() -> dict[str, Any]:
        config = load_config()
        scheduler = LiveScheduler(config)
        try:
            return await scheduler.cycle()
        finally:
            await scheduler.close()

    @app.post("/trade-plan/cycle")
    async def trigger_trade_plan_cycle() -> dict[str, Any]:
        config = load_config()
        orchestrator = TradePlanOrchestrator(config)
        try:
            return await orchestrator.cycle()
        finally:
            await orchestrator.close()

    @app.post("/feedback/cycle")
    async def trigger_feedback_cycle() -> dict[str, Any]:
        config = load_config()
        worker = FeedbackLoopWorker(config)
        try:
            return await worker.cycle()
        finally:
            await worker.close()

    @app.get("/status")
    async def status() -> dict[str, str]:
        return {"status": "idle", "service": "vinu-live"}

    return app
