from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from vinu_initial_analysis.config import load_config
from vinu_initial_analysis.service import InitialAnalysisService
from vinu_initial_analysis.server import routes_config, routes_read, routes_v1
from vinu_infra.server import create_app as _create_app


def create_app(service: InitialAnalysisService | None = None):
    app_service = service or InitialAnalysisService()
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
    routes_v1.get_service = _get_service

    main_router = routes_read.router
    merged = __import__("fastapi").APIRouter()
    merged.include_router(main_router)
    merged.include_router(routes_config.router)

    app = _create_app(
        service_name="vinu-initial-analysis",
        version="0.2.0",
        description="Foundational analysis pipeline — 35 deterministic angles for every stock",
        router=merged,
        lifespan=lifespan,
        static_dir=Path(__file__).parent / "static",
        expose_health_on_root=False,
        route_prefix="analysis",
    )
    # The redesigned positional API — additive, alongside /analysis/* above.
    # See routes_v1.py's module docstring for the full design.
    app.include_router(routes_v1.router, prefix="/v1/stage1/vinu-initial-analysis")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run vinu-initial-analysis HTTP API")
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
