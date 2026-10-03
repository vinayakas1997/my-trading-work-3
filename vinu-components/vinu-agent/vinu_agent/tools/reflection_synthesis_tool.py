"""Step 9 (system-wide-audit-and-design/00-overview.md, 02-open-
questions-strategy-and-simulation.md): the first real consumer of
vinu-reflection's "brain" output (Step 8) -- a read-only, hourly
maturity-synthesis judgment (`narrative_only`/`significance_flag`/
`threshold_nudge`), never an order or a kill-switch action.

Confirmed directly (2026-09-28) that Planner is the first consumer to
wire, not risk_gatekeeper/capital_allocator -- lowest-risk starting
point since Planner doesn't place orders itself, and it already reasons
over other advisory-only signals each cycle.

Over HTTP only, no in-process fallback: unlike `signal_evidence_tool.py`
(vinu-research, a real in-process option via `broker/research_link.py`),
vinu-agent and vinu-reflection share no process -- vinu-reflection
already depends on vinu-agent (it mounts and imports it for its own
analysts' LLM calls), so vinu-agent importing vinu-reflection back would
be the exact circular dependency Step 9's own design note flags.
"""

import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class GetReflectionSynthesisTool(BaseTool):
    name = "get_reflection_synthesis"
    description = (
        "Read the reflection system's most recent maturity-synthesis judgment -- "
        "a read-only, periodic (roughly hourly) assessment of how much the "
        "system's own recent beliefs/evidence can be trusted right now, plus an "
        "optional bounded suggestion (a narrative note, a significance flag, or "
        "a proposed threshold nudge). This is advisory context only: it never "
        "places an order, never touches the kill switch, and may be empty most "
        "cycles ('status': 'none') -- that's expected, not an error. Use this to "
        "factor in a system-level confidence signal alongside whatever else "
        "you're already reasoning about, not as a standalone directive."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        def _record(status: str, detail: str = "") -> None:
            try:
                from vinu_infra.pipeline_edge_recorder import record_edge

                record_edge("reflection.synthesis->agent.idea_generator", status, detail)
            except Exception:  # noqa: BLE001
                pass

        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None

        url = self._services_config.get("vinu_reflection", "http://localhost:8092")
        try:
            resp = httpx.get(f"{url}/reflection/synthesis/latest", headers=_h, timeout=30)
            resp.raise_for_status()
            body = resp.json()
            _record("received" if body else "empty")
            return json.dumps(body)
        except Exception as exc:
            LOG.warning("get_reflection_synthesis: request failed: %s", exc)
            _record("missing", str(exc))
            return json.dumps({"status": "error", "error": str(exc)})
