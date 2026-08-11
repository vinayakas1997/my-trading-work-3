from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter

from vinu_infra.server import create_app as _create_app
from vinu_strategy.server.routes_config import router as config_router
from vinu_strategy.server.routes_read import router as read_router


@asynccontextmanager
async def lifespan(app):
    from vinu_strategy.server.routes_config import set_service
    from vinu_strategy.server.routes_read import _get_api
    api = await asyncio.to_thread(_get_api)
    set_service(api._service)
    yield


def create_app():
    merged = APIRouter()
    merged.include_router(read_router, tags=["read"])
    merged.include_router(config_router, tags=["config"])

    return _create_app(
        service_name="vinu-strategy",
        version="0.1.0",
        description="Decision fusion — combines features + correlation into target portfolio weights",
        router=merged,
        static_dir=Path(__file__).resolve().parent / "static",
        expose_health_on_root=True,
        lifespan=lifespan,
        route_prefix="strategy",
    )
