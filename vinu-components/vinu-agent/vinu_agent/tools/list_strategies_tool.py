import json
from ..agent.tools import BaseTool


class ListStrategiesTool(BaseTool):
    name = "list_strategies"
    description = (
        "List every strategy currently registered with vinu-strategy -- the "
        "real names run_strategy accepts as strategy_name, e.g. "
        "'ma_crossover' or 'rsi_mean_reversion'. Call this before "
        "run_strategy so you don't guess a strategy name and get a 404."
    )
    parameters = {"type": "object", "properties": {}, "required": []}
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_strategy", "http://localhost:8084")
        resp = httpx.get(f"{url}/strategy/strategies", timeout=30)
        resp.raise_for_status()
        strategies = resp.json()
        return json.dumps({"status": "ok", "count": len(strategies), "strategies": strategies})
