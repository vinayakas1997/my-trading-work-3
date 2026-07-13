from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from vinu_correlation.config import load_config
from vinu_correlation.service import CorrelationService
from vinu_correlation.server import routes_config, routes_read
from vinu_lib.server import create_app as _create_app


def create_app(service: CorrelationService | None = None):
    app_service = service or CorrelationService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app):
        yield
        if owns_service:
            await app_service.close()

    def _get_service():
        return app_service

    routes_config.get_service = _get_service
    routes_read.get_service = _get_service

    main_router = routes_read.router
    merged = __import__("fastapi").APIRouter()
    merged.include_router(main_router)
    merged.include_router(routes_config.router)

    return _create_app(
        service_name="vinu-correlation",
        version="0.1.0",
        description="Statistical bridge between news and price — mathematical proof of news impact on price movements",
        router=merged,
        lifespan=lifespan,
        static_dir=Path(__file__).parent / "static",
        expose_health_on_root=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vinu-correlation HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()

    config = load_config()
    if args.host:
        config = config.__class__(**{**config.__dict__, "host": args.host})
    if args.port is not None:
        config = config.__class__(**{**config.__dict__, "port": args.port})
    if args.data_root:
        config = config.__class__(**{**config.__dict__, "data_root": args.data_root})

    import uvicorn
    uvicorn.run(create_app(), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
