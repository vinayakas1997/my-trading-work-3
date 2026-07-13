from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from vinu_correlation.config import load_config
from vinu_correlation.service import CorrelationService
from vinu_correlation.server import routes_config, routes_read


def create_app(service: CorrelationService | None = None) -> FastAPI:
    app_service = service or CorrelationService()
    owns_service = service is None

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        if owns_service:
            app_service.close()

    app = FastAPI(
        title="vinu-correlation",
        description="Statistical bridge between news and price — mathematical proof of news impact on price movements",
        version="0.1.0",
        lifespan=lifespan,
    )

    def _get_service() -> CorrelationService:
        return app_service

    routes_config.get_service = _get_service
    routes_read.get_service = _get_service

    app.include_router(routes_config.router)
    app.include_router(routes_read.router)

    static_dir = Path(__file__).parent / "static"
    if static_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")

    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vinu-correlation HTTP API")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()

    config = load_config()
    if args.host:
        config = config.__class__(
            **{**config.__dict__, "host": args.host}
        )
    if args.port is not None:
        config = config.__class__(
            **{**config.__dict__, "port": args.port}
        )
    if args.data_root:
        config = config.__class__(
            **{**config.__dict__, "data_root": args.data_root}
        )

    import uvicorn
    uvicorn.run(create_app(), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
