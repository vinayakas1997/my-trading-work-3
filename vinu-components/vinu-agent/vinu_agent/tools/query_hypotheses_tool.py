import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class QueryHypothesesTool(BaseTool):
    name = "query_hypotheses"
    description = (
        "Read recorded research hypotheses and their evidence trail — what was "
        "expected before a backtest ran, what the outcome was, and whether it "
        "supported or contradicted the hypothesis. Backed by the same registry "
        "the research loop already writes to during every research run; use "
        "this before starting new research on a symbol to see what's already "
        "been tried and concluded."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Filter to hypotheses whose universe includes this ticker (optional — omit to list all)",
            },
            "status": {
                "type": "string",
                "description": "Filter by status: exploring|testing|validated|rejected|monitoring|mc_gate_failed (optional)",
            },
        },
        "required": [],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        status = kwargs.get("status")
        try:
            from vinu_research.models import HypothesisStatus

            from ..broker.research_link import get_hypothesis_registry, serialize_hypothesis

            status_enum = HypothesisStatus(status) if status else None
            registry = get_hypothesis_registry()
            hypotheses = (
                registry.query_by_symbol(symbol, status=status_enum) if symbol
                else registry.list_all(status=status_enum)
            )
            return json.dumps({
                "count": len(hypotheses),
                "hypotheses": [serialize_hypothesis(h) for h in hypotheses],
            })
        except Exception as exc:
            LOG.debug("query_hypotheses: in-process read failed, falling back to HTTP: %s", exc)

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        params = {}
        if symbol:
            params["symbol"] = symbol
        if status:
            params["status"] = status

        resp = httpx.get(f"{url}/research/hypotheses", params=params, timeout=30)
        resp.raise_for_status()
        return resp.text
