from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter

from vinu_lib.server import create_app as _create_app
from vinu_stock.server import routes_config, routes_read
from vinu_stock.service import StockService


def create_app(service: StockService | None = None):
    app_service = service or StockService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owns_service:
            app_service.close()

    def _get_service():
        return app_service

    routes_config.get_service = _get_service
    routes_read.get_service = _get_service

    merged = APIRouter()
    merged.include_router(routes_read.router)
    merged.include_router(routes_config.router)

    return _create_app(
        service_name="vinu-stock-price",
        version="0.1.0",
        description="Historical and live 1m OHLCV Parquet store with query API",
        router=merged,
        lifespan=lifespan,
        static_dir=Path(__file__).parent / "static",
        expose_health_on_root=False,
    )
