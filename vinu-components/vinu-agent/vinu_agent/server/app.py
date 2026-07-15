import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, FastAPI

from ..config import load_config
from ..service import AgentService


def create_app(service: Any = None) -> FastAPI:
    app_service = service or AgentService()

    import vinu_agent.server.routes_sessions as rs
    import vinu_agent.server.routes_swarm as rw
    import vinu_agent.server.routes_system as rsys

    rs._get_service = lambda: app_service
    rw._get_service = lambda: app_service
    rsys._get_service = lambda: app_service

    merged = APIRouter()
    merged.include_router(rs.router, tags=["sessions"])
    merged.include_router(rw.router, tags=["swarm"])
    merged.include_router(rsys.router, tags=["system"])

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_event_loop()
        app_service.event_bus.set_loop(loop)
        yield

    from vinu_lib.server import create_app as _create_base

    return _create_base(
        service_name="vinu-agent",
        version="0.1.0",
        description="Autonomous ReAct agent for vinu-components",
        router=merged,
        lifespan=_lifespan,
        expose_health_on_root=True,
    )


def run(host: str = "127.0.0.1", port: int = 8086) -> None:
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)
