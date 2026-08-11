import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import APIRouter, FastAPI

from ..config import load_config
from ..service import AgentService

logger = logging.getLogger(__name__)


def _start_channels(app_service: AgentService) -> list[Any]:
    """Start configured notification channel bots."""
    from ..channels.discord import DiscordChannel
    from ..channels.telegram import TelegramChannel

    config = load_config()
    channels: list[Any] = []
    channel_configs = getattr(config, "channels", {})

    tg_config = channel_configs.get("telegram", {})
    if tg_config.get("token"):
        tg = TelegramChannel(tg_config, app_service)
        asyncio.create_task(tg.start())
        channels.append(tg)
        logger.info("Telegram channel started")

    dc_config = channel_configs.get("discord", {})
    if dc_config.get("token"):
        dc = DiscordChannel(dc_config, app_service)
        asyncio.create_task(dc.start())
        channels.append(dc)
        logger.info("Discord channel started")

    return channels


def create_app(service: Any = None) -> FastAPI:
    app_service = service or AgentService()

    import vinu_agent.server.routes_broker as rb
    import vinu_agent.server.routes_sessions as rs
    import vinu_agent.server.routes_swarm as rw
    import vinu_agent.server.routes_system as rsys
    import vinu_agent.server.routes_ticker_ledger as rtl

    rs._get_service = lambda: app_service
    rw._get_service = lambda: app_service
    rsys._get_service = lambda: app_service
    rtl._get_service = lambda: app_service

    merged = APIRouter()
    merged.include_router(rs.router, tags=["sessions"])
    merged.include_router(rw.router, tags=["swarm"])
    merged.include_router(rsys.router, tags=["system"])
    merged.include_router(rb.router, tags=["broker"])
    merged.include_router(rtl.router, tags=["ticker-ledger"])

    _channels: list[Any] = []

    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        loop = asyncio.get_event_loop()
        app_service.event_bus.set_loop(loop)
        _channels.extend(_start_channels(app_service))
        yield
        for ch in _channels:
            try:
                await ch.stop()
            except Exception as e:
                logger.warning("Failed to stop channel %s: %s", ch.name, e)

    from vinu_infra.server import create_app as _create_base

    return _create_base(
        service_name="vinu-agent",
        version="0.1.0",
        description="Autonomous ReAct agent for vinu-components",
        router=merged,
        lifespan=_lifespan,
        expose_health_on_root=True,
        route_prefix="agent",
    )


def run(host: str = "127.0.0.1", port: int = 8086) -> None:
    import uvicorn
    app = create_app()
    uvicorn.run(app, host=host, port=port)
