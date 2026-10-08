"""Read-only view of the capital allocator's answer, for agents that decide about money.

The numbers are not sent to the agent by anyone: this tool reads them where they live (vinu-portfolio's
`/portfolio/capital-plan`, which is built from vinu-live's capital ledger). It shows the real-money base, what open trades
hold, the reserve, the free cash, what each strategy should hold in dollars, who was refused and why, the fail/win cash
scenarios, and the closed-trade results, every figure tagged with the money mode (`account_mode`). Paper figures and real
figures are never mixed in one answer.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class GetCapitalSummaryTool(BaseTool):
    name = "get_capital_summary"
    description = (
        "Read the capital allocator's current answer: the real-money base (for example 20 dollars), money already committed "
        "to open trades, the reserve, the free cash that can still be spent, the dollars each strategy should hold, which "
        "candidates were refused and why, the cash left if a trade fails or wins, and the closed-trade results. Every figure "
        "carries `account_mode` (paper or real). Call this before sizing or funding anything; do not work out free cash "
        "yourself. Read-only."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        url = self._services_config.get("vinu_portfolio", "http://localhost:8090")
        try:
            import httpx

            try:
                from vinu_infra.auth import internal_auth_headers as _iah

                headers = _iah() or None
            except Exception:  # noqa: BLE001
                headers = None
            resp = httpx.get(f"{url}/portfolio/capital-plan", headers=headers, timeout=60.0)
            resp.raise_for_status()
            return json.dumps({"status": "ok", **resp.json()})
        except Exception as exc:  # noqa: BLE001
            LOG.warning("vinu-portfolio unreachable for get_capital_summary: %s", exc)
            return json.dumps({"status": "unavailable", "error": f"vinu-portfolio unreachable: {exc}"})
