"""Discovery tool for vinu-portfolio's real, currently-ACTIVE strategy
book. Component-consolidation-plan.md audit finding: no agent tool ever
called GET /portfolio/strategies (PortfolioService.list_active_strategies())
-- submit_order and compute_allocation_candidates could act on capital with
no way for the agent to first see what vinu-portfolio's engine actually
currently holds/targets, only what raw Alpaca reports (get_portfolio) or
incidental per-symbol context (get_portfolio_concentration).

Same fail-open posture as portfolio_concentration_tool.py -- vinu-portfolio
being briefly unreachable shouldn't hard-fail a context-gathering call.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class ListPortfolioStrategiesTool(BaseTool):
    name = "list_portfolio_strategies"
    description = (
        "List vinu-portfolio's real, currently ACTIVE engine-level "
        "strategies -- name, kind (yaml or llm_python), symbol, and "
        "weights_source for each -- the actual book the correlation-aware "
        "risk-parity engine is allocating across right now. Call this "
        "before submit_order or compute_allocation_candidates to see "
        "what's really active instead of assuming."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        url = self._services_config.get("vinu_portfolio", "http://localhost:8090")
        try:
            import httpx

            resp = httpx.get(f"{url}/portfolio/strategies", timeout=10.0)
            resp.raise_for_status()
            strategies = resp.json()
        except Exception as exc:
            LOG.warning("vinu-portfolio unreachable for list_portfolio_strategies: %s", exc)
            return json.dumps({
                "status": "unavailable",
                "error": f"vinu-portfolio unreachable: {exc}",
                "strategies": [],
            })

        return json.dumps({"status": "ok", "count": len(strategies), "strategies": strategies})
