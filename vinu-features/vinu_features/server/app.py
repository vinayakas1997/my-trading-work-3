"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from vinu_features.server import routes_features, routes_requests
from vinu_features.service import FeatureService


def create_app(service: FeatureService | None = None) -> FastAPI:
    app_service = service or FeatureService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_service:
            app_service.close()

    app = FastAPI(
        title="vinu-features",
        description="Feature run registry and artifact API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _get_service() -> FeatureService:
        return app_service

    routes_requests.get_service = _get_service  # type: ignore[method-assign]
    app.include_router(routes_requests.router)
    app.include_router(routes_features.router)
    return app
