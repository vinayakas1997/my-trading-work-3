import json
import time
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


class FeaturesTool(BaseTool):
    name = "get_features"
    description = "Compute technical indicators (SMA, RSI, MACD, etc.) for a symbol over a date range"
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "indicators": {
                "type": "string",
                "description": "Comma-separated indicator names (e.g., sma_20,rsi_14,macd)",
            },
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        },
        "required": ["symbol", "start_date", "end_date"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_tools", "http://localhost:8082")
        resp = httpx.post(
            f"{url}/features/requests",
            json={
                "symbol": kwargs["symbol"],
                "indicators": kwargs.get("indicators", "sma_20,rsi_14").split(","),
                "from_ts": _date_to_epoch(kwargs["start_date"]),
                "to_ts": _date_to_epoch(kwargs["end_date"]),
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.text
