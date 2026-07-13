"""Shared FastAPI application factory.

Usage:
    from vinu_lib.server import create_app
    from my_service.server import router

    app = create_app("my-service", "0.1.0", "description", router)
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette.staticfiles import StaticFiles


def create_app(
    service_name: str,
    version: str,
    description: str,
    router: APIRouter,
    *,
    lifespan: Callable[[FastAPI], AsyncIterator[None]] | None = None,
    static_dir: Path | None = None,
    config_routes: APIRouter | None = None,
    expose_health_on_root: bool = True,
) -> FastAPI:
    start_time = time.time()

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        if lifespan:
            async with lifespan(app):
                yield
        else:
            yield

    app = FastAPI(
        title=service_name,
        description=description,
        version=version,
        lifespan=_lifespan,
    )

    app.include_router(router)

    if config_routes is not None:
        app.include_router(config_routes)

    if expose_health_on_root:

        @app.get("/health")
        def _health() -> dict[str, Any]:
            return {
                "ok": True,
                "service": service_name,
                "version": version,
                "uptime_sec": round(time.time() - start_time, 2),
            }

    @app.exception_handler(ValueError)
    def _validation_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"detail": str(exc), "error": "validation_error"},
        )

    if static_dir and static_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    return app
