from __future__ import annotations

from fastapi import APIRouter

from vinu_lib.server import create_app as _create_app
from vinu_research.service import ResearchService
from vinu_research.server import routes_config, routes_read, routes_trade_plan


def create_app(service: ResearchService | None = None):
    app_service = service or ResearchService()
    routes_config.set_service(app_service)
    routes_read.set_service(app_service)
    routes_trade_plan.set_service(app_service)

    merged = APIRouter()
    merged.include_router(routes_read.router, tags=["read"])
    merged.include_router(routes_config.router, tags=["config"])
    merged.include_router(routes_trade_plan.router, tags=["trade-plan"])

    return _create_app(
        service_name="vinu-research",
        version="0.1.0",
        description="Agentic Strategy Researcher — multi-agent loop for generating, backtesting, and refining strategies",
        router=merged,
        static_dir=None,
        expose_health_on_root=False,
    )
