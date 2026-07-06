from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from vinu_strategy.server.routes_read import router as read_router
from vinu_strategy.server.routes_config import router as config_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="vinu-strategy",
        description="Decision fusion — combines features + correlation into target portfolio weights",
        version="0.1.0",
    )

    app.include_router(read_router, prefix="", tags=["read"])
    app.include_router(config_router, prefix="", tags=["config"])

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app
