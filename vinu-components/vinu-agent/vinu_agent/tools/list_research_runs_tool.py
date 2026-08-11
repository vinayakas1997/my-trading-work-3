import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class ListResearchRunsTool(BaseTool):
    name = "list_research_runs"
    description = (
        "List past and in-progress vinu-research runs -- each run's id, "
        "symbol, status, best_sharpe, and iteration count. Use this to find "
        "a run_id for get_run_checkpoints, or to check whether a symbol "
        "already has research runs before starting a new one with "
        "run_research."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Filter to runs for this symbol (optional)"},
            "status": {"type": "string", "description": "Filter by run status (optional)"},
            "limit": {"type": "integer", "description": "Max runs to return (optional, default 50)"},
        },
        "required": [],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        symbol = kwargs.get("symbol")
        status = kwargs.get("status")
        limit = int(kwargs.get("limit", 50))
        try:
            from ..broker.research_link import get_research_storage

            storage = get_research_storage()
            runs = storage.list_runs(symbol=symbol, status=status, limit=limit)
            return json.dumps({"count": len(runs), "runs": [r.to_dict() for r in runs]})
        except Exception as exc:
            LOG.debug("list_research_runs: in-process read failed, falling back to HTTP: %s", exc)

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        params = {"limit": limit}
        if symbol:
            params["symbol"] = symbol
        if status:
            params["status"] = status

        resp = httpx.get(f"{url}/research/runs", params=params, timeout=30)
        resp.raise_for_status()
        return resp.text
