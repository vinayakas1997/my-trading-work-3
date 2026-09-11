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

    # Stage 0 (G2b): the /approve_plan command handler POSTs directly to
    # vinu-research's approve endpoint, same URL every other tool in this
    # service already reads from config.services["vinu_research"].
    research_api_url = config.services.get("vinu_research", "http://localhost:8087")

    # /rank and /track (channels/telegram.py) need the screener, news, and
    # stock-price base URLs -- passed through the same "services" dict every
    # agent tool already reads (config.services), not new env plumbing.
    tg_config = {
        **channel_configs.get("telegram", {}),
        "research_api_url": research_api_url,
        "services": config.services,
    }
    if tg_config.get("token"):
        tg = TelegramChannel(tg_config, app_service)
        asyncio.create_task(tg.start())
        channels.append(tg)
        logger.info("Telegram channel started")

    dc_config = {**channel_configs.get("discord", {}), "research_api_url": research_api_url}
    if dc_config.get("token"):
        dc = DiscordChannel(dc_config, app_service)
        asyncio.create_task(dc.start())
        channels.append(dc)
        logger.info("Discord channel started")

    return channels


def create_app(service: Any = None) -> FastAPI:
    app_service = service or AgentService()

    import vinu_agent.server.routes_broker as rb
    import vinu_agent.server.routes_notify as rn
    import vinu_agent.server.routes_sessions as rs
    import vinu_agent.server.routes_swarm as rw
    import vinu_agent.server.routes_system as rsys
    import vinu_agent.server.routes_ticker_ledger as rtl
    import vinu_agent.server.routes_trace as rtr
    from vinu_agent.broker.mandate import SETTINGS as MANDATE_SETTINGS
    from vinu_infra.runtime_settings import build_admin_settings_router

    rs._get_service = lambda: app_service
    rw._get_service = lambda: app_service
    rsys._get_service = lambda: app_service
    rtl._get_service = lambda: app_service
    rtr._get_service = lambda: app_service

    merged = APIRouter()
    merged.include_router(rs.router, tags=["sessions"])
    merged.include_router(rw.router, tags=["swarm"])
    merged.include_router(rsys.router, tags=["system"])
    merged.include_router(rb.router, tags=["broker"])
    merged.include_router(rtl.router, tags=["ticker-ledger"])
    merged.include_router(rn.router, tags=["notify"])
    merged.include_router(rtr.router, tags=["trace"])
    # Live-tunable mandate risk limits -- GET/PATCH under
    # /agent/admin/settings, gated by the same require_auth as every other
    # route on this router (wired in by vinu_infra.server.create_app below).
    # A15/A21: every runtime change to a risk limit (max_order_value,
    # max_position_pct, ...) lands in the same trade_audit.log the kill
    # switch and every order write to, so "who loosened the notional cap
    # right before that loss" is answerable after the fact.
    def _audit_settings_change(action: str, changes: dict[str, Any]) -> None:
        from vinu_agent.broker.kill_switch import AuditLogger

        AuditLogger.log(
            AuditLogger.RUNTIME_SETTING_CHANGED,
            {"action": action, "changes": changes},
        )

    merged.include_router(
        build_admin_settings_router(MANDATE_SETTINGS, on_change=_audit_settings_change),
        tags=["admin"],
    )

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
