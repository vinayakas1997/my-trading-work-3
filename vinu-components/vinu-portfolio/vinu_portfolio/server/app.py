from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI

from vinu_portfolio.service import PortfolioService


def create_app() -> FastAPI:
    app = FastAPI(title="vinu-portfolio", version="0.1.0")
    _service = PortfolioService()

    @app.on_event("shutdown")
    async def shutdown() -> None:
        await _service.close()

    router = APIRouter(prefix="/portfolio")

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "vinu-portfolio"}

    @router.get("/state")
    async def get_portfolio() -> dict[str, Any]:
        return await _service.build_portfolio()

    @router.get("/strategies")
    async def list_strategies() -> list[dict[str, Any]]:
        return await _service.list_active_strategies()

    @router.get("/weights")
    async def get_weights() -> list[dict[str, Any]]:
        portfolio = await _service.build_portfolio()
        return portfolio.get("weights", [])

    app.include_router(router)
    return app
