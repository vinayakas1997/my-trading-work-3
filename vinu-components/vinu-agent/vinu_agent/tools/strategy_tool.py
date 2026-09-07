import json
from ..agent.tools import BaseTool


class StrategyTool(BaseTool):
    name = "run_strategy"
    description = "Evaluate a YAML-defined strategy from the strategy service"
    parameters = {
        "type": "object",
        "properties": {
            "strategy_name": {"type": "string", "description": "Name of the registered strategy (use list_strategies to see valid names)"},
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
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None
        url = self._services_config.get("vinu_strategy", "http://localhost:8084")
        resp = httpx.post(
            f"{url}/strategy/strategies/{kwargs['strategy_name']}/evaluate",
            params={"symbols": kwargs["symbol"]},
            headers=_h,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.text
