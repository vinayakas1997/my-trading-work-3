import json
from typing import Any

from ..agent.tools import BaseTool


class FindTradePlanArtifactTool(BaseTool):
    name = "find_trade_plan_artifact"
    description = (
        "Find whether this ticker has an associated type='trade_plan' strategy artifact -- the "
        "input get_trade_plan_calibration needs. Returns the artifact_id if one exists (any "
        "status), or status='not_found' if this ticker has none -- most tickers won't, that's "
        "expected, not an error."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
        },
        "required": ["symbol"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs: Any) -> str:
        symbol = kwargs["symbol"].strip().upper()
        artifacts = self._fetch_trade_plan_artifacts()
        if artifacts is None:
            return json.dumps({"status": "error", "error": "vinu-research unreachable (in-process and HTTP both failed)"})

        for artifact in artifacts:
            universe = [u.upper() for u in artifact.get("universe", [])]
            if symbol in universe:
                return json.dumps({
                    "status": "ok", "artifact_id": artifact.get("artifact_id"),
                    "artifact_status": artifact.get("status"),
                })

        return json.dumps({"status": "not_found", "symbol": symbol})

    def _fetch_trade_plan_artifacts(self) -> list[dict] | None:
        try:
            from ..broker.research_link import get_strategy_store, serialize_artifact_summary

            store = get_strategy_store()
            artifacts = store.list_artifacts_by_statuses(statuses=None, type_="trade_plan")
            return [serialize_artifact_summary(a) for a in artifacts]
        except Exception:
            pass

        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        try:
            resp = httpx.get(f"{url}/research/artifacts", params={"type_": "trade_plan"}, timeout=15)
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None
