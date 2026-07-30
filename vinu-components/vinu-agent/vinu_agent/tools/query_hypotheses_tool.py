from ..agent.tools import BaseTool


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
        "symbol": {
            "type": "string",
            "description": "Filter to hypotheses whose universe includes this ticker (optional — omit to list all)",
        },
        "status": {
            "type": "string",
            "description": "Filter by status: exploring|testing|validated|rejected|monitoring|mc_gate_failed (optional)",
        },
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        params = {}
        if kwargs.get("symbol"):
            params["symbol"] = kwargs["symbol"]
        if kwargs.get("status"):
            params["status"] = kwargs["status"]

        resp = httpx.get(f"{url}/research/hypotheses", params=params, timeout=30)
        resp.raise_for_status()
        return resp.text
