"""HTTP-exposed kill switch — the networked front door onto broker/kill_switch.py.

Every vinu-* service runs in its own container with a private tmpfs /tmp
(see docker-compose.yml), so a kill switch based on touching a local file is
only ever visible within the one container that touched it. OrderGuard checks
the kill switch from inside agent-api, so any other service (vinu-portfolio's
drawdown monitor, a human operator, a future automated monitor) that needs to
halt trading has to do it through this HTTP endpoint, not by touching a file
of its own.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from ..broker.alpaca import AlpacaBroker
from ..broker.kill_switch import halt_trading, is_trading_halted, resume_trading
from ..tools.trade_tool import TradeTool

router = APIRouter()


class HaltRequest(BaseModel):
    scope: str | None = None
    reason: str | None = None


class ResumeRequest(BaseModel):
    scope: str | None = None


@router.post("/broker/halt")
async def broker_halt(body: HaltRequest = HaltRequest()) -> dict[str, Any]:
    halt_trading(scope=body.scope)
    return {"status": "ok", "halted": True, "scope": body.scope, "reason": body.reason}


@router.post("/broker/resume")
async def broker_resume(body: ResumeRequest = ResumeRequest()) -> dict[str, Any]:
    resume_trading(scope=body.scope)
    return {"status": "ok", "halted": False, "scope": body.scope}


@router.get("/broker/status")
async def broker_status(scope: str | None = None) -> dict[str, Any]:
    return {"halted": is_trading_halted(scope=scope), "scope": scope}


@router.get("/broker/account")
async def broker_account() -> dict[str, Any]:
    """Current account equity — the one place other services (e.g. vinu-portfolio's
    drawdown monitor) should get this from, rather than each holding its own
    broker credentials. Returns configured=False (not an error) until a broker
    account exists, so callers can treat that as "no signal yet", not a failure.
    """
    broker = AlpacaBroker()
    if not broker.is_configured():
        return {"configured": False, "equity": None, "cash": None}
    try:
        account = broker.get_account()
        return {
            "configured": True,
            "equity": account.equity,
            "cash": account.cash,
            "portfolio_value": account.portfolio_value,
        }
    except Exception as e:
        return {"configured": True, "equity": None, "cash": None, "error": str(e)}


@router.get("/broker/positions")
async def broker_positions() -> list[dict[str, Any]]:
    broker = AlpacaBroker()
    if not broker.is_configured():
        return []
    positions = await asyncio.to_thread(broker.get_positions)
    return [asdict(p) for p in positions]


class OrderRequest(BaseModel):
    symbol: str
    side: str
    qty: float
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None
    time_in_force: str = "day"
    take_profit_price: float | None = None
    stop_loss_price: float | None = None
    stop_loss_limit_price: float | None = None


@router.post("/broker/order")
async def broker_order(body: OrderRequest) -> dict[str, Any]:
    """Networked front door onto TradeTool — deliberately reuses the exact same
    OrderGuard checks (kill switch, mandate limits, artifact gate, market hours)
    as the LLM's submit_order tool, not a shortcut around them. Any caller that
    needs to place a live order (vinu-live's scheduler included) goes through
    this, not a direct AlpacaBroker.submit_order() call, so the safety layer
    can't be silently bypassed by a second code path.
    """
    tool = TradeTool()
    result_json = await asyncio.to_thread(tool.execute, **body.model_dump())
    return json.loads(result_json)
