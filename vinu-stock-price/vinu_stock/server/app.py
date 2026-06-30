"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from vinu_stock.server import routes_config, routes_read
from vinu_stock.service import StockService


def create_app(service: StockService | None = None) -> FastAPI:
    app_service = service or StockService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_service:
            app_service.close()

    app = FastAPI(
        title="vinu-stock-price",
        description="Historical and live 1m OHLCV Parquet store with query API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _get_service() -> StockService:
        return app_service

    routes_config.get_service = _get_service  # type: ignore[method-assign]
    routes_read.get_service = _get_service  # type: ignore[method-assign]

    app.include_router(routes_config.router)
    app.include_router(routes_read.router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    return app
