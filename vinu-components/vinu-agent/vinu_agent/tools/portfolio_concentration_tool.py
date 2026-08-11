"""Read-only vinu-portfolio concentration context for risk_gatekeeper's
exposure_reviewer specialist (component-consolidation-plan.md: "wire
risk_gatekeeper's exposure check against vinu-portfolio's real engine
instead of deciding new math"). Confirmed by reading the code directly
this session: exposure_reviewer's concentration check was entirely
self-contained -- a hardcoded ~20% rule against raw broker data
(broker.get_account()/get_positions() via portfolio_tool.py), with zero
vinu-portfolio involvement, unlike capital_allocator's funding sizing
(allocation_tool.py), which already calls vinu-portfolio's real
risk-parity engine.

Deliberately additive, not a replacement: the raw-broker 20% check stays
(it answers "what do I actually hold right now," which vinu-portfolio's
own target-weight view can't -- vinu-portfolio's weights are the
engine's current intent across the whole correlation-aware book, a
different and complementary signal). This mirrors OrderGuard's own
`_check_portfolio_concentration` (order_guard.py), which already treats
vinu-portfolio as one more defense-in-depth check alongside its other
gates, not the sole source of truth -- same real GET /portfolio/state
call, same fail-open posture on unreachability.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class GetPortfolioConcentrationTool(BaseTool):
    name = "get_portfolio_concentration"
    description = (
        "Fetch vinu-portfolio's real, live, correlation-aware target-weight state for a "
        "symbol (the same GET /portfolio/state data OrderGuard's own order-time concentration "
        "check uses) -- the symbol's current target_weight (0.0 if not currently held/targeted "
        "by the portfolio engine) plus every other symbol's weight, so a concentration "
        "judgment can be grounded in the whole book's real state, not just this one symbol's "
        "raw position. Complements get_portfolio, not a replacement for it -- vinu-portfolio's "
        "weights reflect the engine's current intent across the whole correlation-aware book, "
        "a different signal from raw current holdings."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Ticker symbol to check concentration for"},
        },
        "required": ["symbol"],
    }
    is_readonly = True
    _services_config: dict = {}

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        symbol = str(kwargs.get("symbol", "")).strip().upper()
        if not symbol:
            return json.dumps({"status": "error", "error": "symbol is required"})

        url = self._services_config.get("vinu_portfolio", "http://localhost:8090")
        try:
            import httpx

            resp = httpx.get(f"{url}/portfolio/state", timeout=10.0)
            resp.raise_for_status()
            portfolio = resp.json()
        except Exception as exc:
            # Fail-open, same posture as every other vinu-portfolio-
            # dependent check in this codebase (order_guard.py's own
            # concentration check, allocation_tool.py) -- this is
            # additional context for exposure_reviewer's judgment, not
            # the only gate; the raw-broker 20% check still runs
            # regardless of whether vinu-portfolio answers.
            LOG.warning("vinu-portfolio unreachable for concentration check on %s: %s", symbol, exc)
            return json.dumps({
                "status": "unavailable",
                "symbol": symbol,
                "error": f"vinu-portfolio unreachable: {exc}",
            })

        weights = portfolio.get("weights") or []
        existing_weight = sum(
            w.get("target_weight", 0.0) for w in weights if w.get("symbol") == symbol
        )
        return json.dumps({
            "status": "ok",
            "symbol": symbol,
            "existing_target_weight": existing_weight,
            "all_weights": [
                {"symbol": w.get("symbol"), "target_weight": w.get("target_weight", 0.0)}
                for w in weights
            ],
        }, indent=2)
