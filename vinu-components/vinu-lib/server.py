"""Shared FastAPI application factory.

Usage:
    from vinu_lib.server import create_app
    from my_service.server import router

    app = create_app("my-service", "0.1.0", "description", router)

Security:
    - CORS: enabled when VINU_CORS_ORIGINS env var is set (comma-separated).
    - Auth: opt-in bearer token auth when VINU_API_KEY env var is set.
"""

from __future__ import annotations

import math
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Callable

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from starlette.staticfiles import StaticFiles

from vinu_lib.auth import VINU_API_KEY, require_auth


def _replace_nan(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _replace_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_replace_nan(v) for v in obj]
    if isinstance(obj, float) and math.isnan(obj):
        return None
    return obj


_original_render = JSONResponse.render
def _safe_render(self, content: Any) -> bytes:
    return _original_render(self, _replace_nan(content))
JSONResponse.render = _safe_render


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

    # CORS — opt-in via VINU_CORS_ORIGINS
    cors_origins = os.getenv("VINU_CORS_ORIGINS", "")
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in cors_origins.split(",") if o.strip()],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Auth — opt-in via VINU_API_KEY (checked inside require_auth)
    auth_deps = [Depends(require_auth)] if VINU_API_KEY else []

    app.include_router(router, dependencies=auth_deps)

    if config_routes is not None:
        app.include_router(config_routes, dependencies=auth_deps)

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
