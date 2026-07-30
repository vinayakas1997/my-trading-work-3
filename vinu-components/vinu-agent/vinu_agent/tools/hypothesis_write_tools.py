from ..agent.tools import BaseTool


class CreateHypothesisTool(BaseTool):
    name = "create_hypothesis"
    description = (
        "Record an expectation/reasoning BEFORE seeing a result — e.g. "
        "before running a coarse pass or a widen/narrow decision in a "
        "parameter sweep. Returns a hypothesis_id; pass it to "
        "add_hypothesis_evidence once the result is in, so 'was this "
        "expectation correct' is checkable afterward via query_hypotheses."
    )
    parameters = {
        "title": {"type": "string", "description": "Short label for this expectation"},
        "thesis": {"type": "string", "description": "The actual expectation/reasoning, in prose"},
        "symbol": {"type": "string", "description": "Primary ticker this hypothesis is about (optional)"},
        "strategy_type": {"type": "string", "description": "Strategy/recipe this hypothesis concerns (optional)"},
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {"title": kwargs["title"], "thesis": kwargs["thesis"]}
        if kwargs.get("symbol"):
            payload["universe"] = [kwargs["symbol"].upper()]
        if kwargs.get("strategy_type"):
            payload["strategy_type"] = kwargs["strategy_type"]

        resp = httpx.post(f"{url}/research/hypotheses", json=payload, timeout=30)
        resp.raise_for_status()
        return resp.text


class AddHypothesisEvidenceTool(BaseTool):
    name = "add_hypothesis_evidence"
    description = (
        "Record what actually happened against a previously-created "
        "hypothesis (via create_hypothesis) — the outcome, whether it "
        "supported or contradicted the expectation, and why. This is what "
        "makes a past expectation checkable later."
    )
    parameters = {
        "hypothesis_id": {"type": "string", "description": "From a prior create_hypothesis call"},
        "metric": {"type": "string", "description": "Which metric this evidence is about, e.g. 'sharpe'"},
        "value": {"type": "number", "description": "The observed value of that metric"},
        "conclusion": {"type": "string", "description": "'supports' or 'contradicts' the hypothesis"},
        "reasoning": {"type": "string", "description": "Why this outcome supports/contradicts the expectation (optional)"},
        "run_id": {"type": "integer", "description": "Associated research run id, if any (optional)"},
        "iteration": {"type": "integer", "description": "Associated iteration/round number, if any (optional)"},
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {
            "metric": kwargs["metric"],
            "value": kwargs["value"],
            "conclusion": kwargs["conclusion"],
        }
        if kwargs.get("reasoning"):
            payload["reasoning"] = kwargs["reasoning"]
        if kwargs.get("run_id") is not None:
            payload["run_id"] = kwargs["run_id"]
        if kwargs.get("iteration") is not None:
            payload["iteration"] = kwargs["iteration"]

        resp = httpx.post(
            f"{url}/research/hypotheses/{kwargs['hypothesis_id']}/evidence",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text
