"""FastAPI application factory."""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import APIRouter

from vinu_lib.server import create_app as _create_app
from vinu_news.config import load_config
from vinu_news.server import routes_config, routes_read
from vinu_news.service import NewsService


def create_app(service: NewsService | None = None):
    app_service = service or NewsService()
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
        service_name="vinu-news",
        version="0.1.0",
        description="Financial news ingestion and query API",
        router=merged,
        lifespan=lifespan,
        static_dir=Path(__file__).parent / "static",
        expose_health_on_root=False,
        route_prefix="news",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vinu-news HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    cfg = load_config()
    host = args.host or cfg.host
    port = args.port or cfg.port
    app = create_app()
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
