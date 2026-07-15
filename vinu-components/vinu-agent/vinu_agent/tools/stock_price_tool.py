import json
import time
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


class StockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Fetch historical OHLCV price data for a symbol"
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        "interval": {
            "type": "string",
            "description": "Bar interval: 1m, 5m, 15m, 1h, 1D (default: 1D)",
        },
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_stock_price", "http://localhost:8081")
        resp = httpx.get(
            f"{url}/candles/{kwargs['symbol'].upper()}",
            params={
                "from": _date_to_epoch(kwargs["start_date"]),
                "to": _date_to_epoch(kwargs["end_date"]),
                "interval": kwargs.get("interval", "1d"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text
