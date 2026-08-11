"""Read-only context for capital_allocator's rebalancer role (New-talk-
agents/new-thinking/new-restructure/mermaid-explanation.md section 5:
"nothing decides whether an existing, weaker ACTIVE strategy should be
unwound to make room for a demonstrably better new one that just cleared
the gate"). Surfaces each ACTIVE artifact's real, computed calibration
history (agent/trade_plan_calibration.py's get_trade_plan_calibration --
the one grounded per-artifact quality signal that actually exists; there
is no per-angle calibration tracker, see calibration.py) so an
unwind-to-fund decision can be traced back to real forecast-accuracy data
instead of an invented score. Never decides anything itself -- the
manager's own final JSON answer (an optional "unwind" list) is the
decision; agent/capital_allocator_hook.py applies it, same "compute here,
mutate from the parsed final answer" split as compute_allocation_candidates.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class ListActiveArtifactsForRebalanceTool(BaseTool):
    name = "list_active_artifacts_for_rebalance"
    description = (
        "List currently ACTIVE strategy artifacts (real, funded positions) with each one's "
        "risk_gatekeeper-approved size and real calibration history, so an unwind-to-fund "
        "decision can be grounded in actual forecast-accuracy data rather than a guess. "
        "Read-only -- deciding to request an unwind happens in your own final answer's "
        "'unwind' list, never here."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tickers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional: restrict to these tickers' ACTIVE artifacts. Omit for every ACTIVE artifact.",
            },
        },
        "required": [],
    }
    is_readonly = True
    _strategy_store: Any = None
    _services_config: dict = {}

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        if self._strategy_store is None:
            return json.dumps({"status": "error", "error": "strategy_store not configured"})

        from vinu_research.models import ArtifactStatus

        from ..agent.trade_plan_calibration import get_trade_plan_calibration

        wanted = kwargs.get("tickers") or None
        artifacts = self._strategy_store.list_artifacts_by_statuses([ArtifactStatus.ACTIVE])
        if wanted:
            wanted_upper = {t.upper() for t in wanted}
            artifacts = [
                a for a in artifacts
                if a.universe and a.universe[0].upper() in wanted_upper
            ]

        research_url = self._services_config.get("vinu_research", "http://localhost:8087")
        out = []
        for a in artifacts:
            calibration = get_trade_plan_calibration(a.artifact_id, research_api_url=research_url)
            out.append({
                "artifact_id": a.artifact_id,
                "name": a.name,
                "symbol": a.universe[0] if a.universe else "",
                "approved_size": a.approved_size,
                "calibration": calibration,
            })

        return json.dumps({"status": "ok", "active_artifacts": out}, indent=2)
