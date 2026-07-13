from __future__ import annotations

from fastapi import FastAPI

from vinu_research.service import ResearchService
from vinu_research.server import routes_config, routes_read


def create_app(service: ResearchService | None = None) -> FastAPI:
    app_service = service or ResearchService()
    owns_service = service is None

    routes_config.set_service(app_service)
    routes_read.set_service(app_service)

    app = FastAPI(
        title="vinu-research",
        description="Agentic Strategy Researcher — multi-agent loop for generating, backtesting, and refining strategies",
        version="0.1.0",
    )

    app.include_router(routes_config.router, prefix="", tags=["config"])
    app.include_router(routes_read.router, prefix="", tags=["read"])

    return app
