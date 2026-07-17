from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import APIRouter

from vinu_lib.server import create_app as _create_app
from vinu_tools.server import routes_features, routes_requests
from vinu_tools.service import FeatureService


def create_app(service: FeatureService | None = None):
    app_service = service or FeatureService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owns_service:
            app_service.close()

    routes_requests.set_service(app_service)

    merged = APIRouter()
    merged.include_router(routes_requests.router)
    merged.include_router(routes_features.router)

    return _create_app(
        service_name="vinu-tools",
        version="0.1.0",
        description="Feature run registry and artifact API",
        router=merged,
        lifespan=lifespan,
        static_dir=None,
        expose_health_on_root=True,
    )
