import json
import logging

from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


def _serialize_brief(h) -> dict:
    """routes_hypothesis.py's own `_serialize` shape (deliberately smaller
    than research_link.serialize_hypothesis, which mirrors the fuller
    routes_introspect.py shape instead) -- kept local since it's specific
    to this HTTP route's own response contract."""
    return {
        "hypothesis_id": h.hypothesis_id,
        "title": h.title,
        "thesis": h.thesis,
        "status": h.status.value,
        "universe": h.universe,
        "strategy_type": h.strategy_type,
        "best_sharpe": h.best_sharpe,
        "evidence_count": len(h.evidence),
        "created_at": h.created_at,
        "updated_at": h.updated_at,
        "source": h.source,
    }


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
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Short label for this expectation"},
            "thesis": {"type": "string", "description": "The actual expectation/reasoning, in prose"},
            "symbol": {"type": "string", "description": "Primary ticker this hypothesis is about (optional)"},
            "strategy_type": {"type": "string", "description": "Strategy/recipe this hypothesis concerns (optional)"},
        },
        "required": ["title", "thesis"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        universe = [kwargs["symbol"].upper()] if kwargs.get("symbol") else []
        try:
            from vinu_research.models import Hypothesis

            from ..broker.research_link import get_hypothesis_registry

            h = Hypothesis.create(title=kwargs["title"], thesis=kwargs["thesis"], universe=universe)
            if kwargs.get("strategy_type"):
                h.strategy_type = kwargs["strategy_type"]
            get_hypothesis_registry().create(h)
            return json.dumps(_serialize_brief(h))
        except Exception as exc:
            LOG.debug("create_hypothesis: in-process write failed, falling back to HTTP: %s", exc)

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        payload = {"title": kwargs["title"], "thesis": kwargs["thesis"]}
        if kwargs.get("symbol"):
            payload["universe"] = universe
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
        "type": "object",
        "properties": {
            "hypothesis_id": {"type": "string", "description": "From a prior create_hypothesis call"},
            "metric": {"type": "string", "description": "Which metric this evidence is about, e.g. 'sharpe'"},
            "value": {"type": "number", "description": "The observed value of that metric"},
            "conclusion": {"type": "string", "description": "'supports' or 'contradicts' the hypothesis"},
            "reasoning": {"type": "string", "description": "Why this outcome supports/contradicts the expectation (optional)"},
            "run_id": {"type": "integer", "description": "Associated research run id, if any (optional)"},
            "iteration": {"type": "integer", "description": "Associated iteration/round number, if any (optional)"},
        },
        "required": ["hypothesis_id", "metric", "value", "conclusion"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        hypothesis_id = kwargs["hypothesis_id"]
        try:
            from vinu_research.models import Evidence

            from ..broker.research_link import get_hypothesis_registry

            evidence = Evidence(
                run_id=kwargs.get("run_id") or 0,
                iteration=kwargs.get("iteration") or 0,
                metric=kwargs["metric"],
                value=kwargs["value"],
                conclusion=kwargs["conclusion"],
                reasoning=kwargs.get("reasoning", ""),
            )
            h = get_hypothesis_registry().add_evidence(hypothesis_id, evidence)
            if h is None:
                raise ValueError(f"Hypothesis {hypothesis_id} not found")
            return json.dumps(_serialize_brief(h))
        except Exception as exc:
            LOG.debug("add_hypothesis_evidence: in-process write failed, falling back to HTTP: %s", exc)

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
            f"{url}/research/hypotheses/{hypothesis_id}/evidence",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text
