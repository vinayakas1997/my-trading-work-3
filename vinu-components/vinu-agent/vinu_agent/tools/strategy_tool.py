import json
from ..agent.tools import BaseTool


class StrategyTool(BaseTool):
    name = "run_strategy"
    description = "Evaluate a YAML-defined strategy from the strategy service"
    parameters = {
        "type": "object",
        "properties": {
            "strategy_name": {"type": "string", "description": "Name of the registered strategy"},
            "symbol": {"type": "string", "description": "Stock symbol"},
            "date": {"type": "string", "description": "Evaluation date YYYY-MM-DD (optional, currently unused)"},
        },
        "required": ["strategy_name", "symbol"],
    }
    is_readonly = False

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_strategy", "http://localhost:8084")
        resp = httpx.post(
            f"{url}/strategies/{kwargs['strategy_name']}/evaluate",
            params={"symbols": kwargs["symbol"]},
            timeout=60,
        )
        resp.raise_for_status()
        return resp.text
