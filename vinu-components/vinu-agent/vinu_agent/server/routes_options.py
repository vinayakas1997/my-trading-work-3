"""HTTP-exposed options chain snapshot -- the networked front door onto
tools/options_tool.py's fetch_chain(), the same convention routes_broker.py
uses for kill_switch (a plain function wrapped in a route, not the
BaseTool/LLM-tool wrapper).

vinu-research needs this data for the high-expectations spec's options-IV
wiring (trade_plan_authoring.py's fetch_options_context) but cannot call an
LLM tool directly (Rule 10: "no LLM outside vinu-research") and shouldn't
hold its own Alpaca credentials when vinu-agent's options_tool.py already
does -- so this route is the one place that data crosses the service
boundary, over HTTP like every other cross-service read in this codebase.

Live snapshot only (today's data, no historical lookup) -- same limitation
fetch_chain itself documents; this route doesn't add or remove that.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter

from ..tools.options_tool import fetch_chain

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/options/{symbol}/snapshot")
async def get_options_snapshot(
    symbol: str, expiration: str | None = None, limit: int = 100,
) -> dict[str, Any]:
    """Mirrors OptionsGreeksTool.execute()'s status/contracts shape (status:
    ok/empty/error) rather than raising on every failure -- a missing
    options entitlement or an empty chain (symbol has no listed options) is
    routine, not a 5xx-worthy server error, and ResearchTools.get_options_
    snapshot already treats anything but status=="ok" as "unavailable"."""
    symbol = symbol.upper()
    try:
        # fetch_chain is a synchronous `requests` call (options_tool.py) --
        # run off the event loop so one slow/hanging Alpaca request doesn't
        # block every other request this process is serving.
        rows = await asyncio.to_thread(fetch_chain, symbol, limit, expiration)
    except Exception as e:
        logger.warning("Options snapshot fetch failed for %s: %s", symbol, e)
        return {"status": "error", "symbol": symbol, "error": str(e)}
    if not rows:
        return {"status": "empty", "symbol": symbol, "n_contracts": 0, "contracts": []}
    return {"status": "ok", "symbol": symbol, "n_contracts": len(rows), "contracts": rows}
