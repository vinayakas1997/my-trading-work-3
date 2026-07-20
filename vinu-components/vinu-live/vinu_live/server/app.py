from __future__ import annotations

from typing import Any

from fastapi import FastAPI

from vinu_live.config import load_config
from vinu_live.scheduler import LiveScheduler


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

    @app.get("/status")
    async def status() -> dict[str, str]:
        return {"status": "idle", "service": "vinu-live"}

    return app
