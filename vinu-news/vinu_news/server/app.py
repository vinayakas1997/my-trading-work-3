"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from vinu_news.server import routes_config, routes_read
from vinu_news.server.schemas import IngestTriggerResponse
from vinu_news.service import NewsService


def create_app(service: NewsService | None = None) -> FastAPI:
    """Build FastAPI app with shared NewsService."""
    app_service = service or NewsService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_service:
            app_service.close()

    app = FastAPI(
        title="vinu-news",
        description="Financial news ingestion and query API",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _get_service() -> NewsService:
        return app_service

    routes_config.get_service = _get_service  # type: ignore[method-assign]
    routes_read.get_service = _get_service  # type: ignore[method-assign]

    app.include_router(routes_config.router)
    app.include_router(routes_read.router)

    @app.post("/ingest/trigger", response_model=IngestTriggerResponse, tags=["ingest"])
    def trigger_ingest() -> IngestTriggerResponse:
        result = app_service.run_ingestion_cycle()
        return IngestTriggerResponse(
            ok=True,
            summary={
                "inserted": result.inserted,
                "mode": result.mode,
                "leads_after_filter": result.leads_after_filter,
                "raw_count": result.raw_count,
            },
        )

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    return app


def main() -> None:
    import argparse

    import uvicorn

    from vinu_news.config import load_config

    parser = argparse.ArgumentParser(description="Run vinu-news HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config()
    host = args.host or cfg.host
    port = args.port or cfg.port
    app = create_app()
    uvicorn.run(app, host=host, port=port)
