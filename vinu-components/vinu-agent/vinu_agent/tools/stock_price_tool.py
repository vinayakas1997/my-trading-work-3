import json
import time
from datetime import datetime, timezone
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


def _iso_to_epoch(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp())


class StockPriceTool(BaseTool):
    name = "get_stock_price"
    description = "Fetch historical OHLCV price data for a symbol"
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD (defaults to 30 days back)"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD (defaults to the decision date)"},
            "interval": {
                "type": "string",
                "description": "Bar interval: 1m, 5m, 15m, 1h, 1D (default: 1D)",
            },
        },
        "required": ["symbol"],
    }
    is_readonly = True
    _as_of: str | None = None
    _session_id: str = ""

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_stock_price", "http://localhost:8081")
        as_of_epoch = _iso_to_epoch(self._as_of) if self._as_of else int(time.time())
        # Defaults keep the tool usable when the model omits a date, and clamp
        # to the replay decision point so the agent can never see post-as_of data.
        end_epoch = _date_to_epoch(kwargs["end_date"]) if kwargs.get("end_date") else as_of_epoch
        start_epoch = (
            _date_to_epoch(kwargs["start_date"])
            if kwargs.get("start_date")
            else as_of_epoch - 30 * 86400
        )
        clamped = False
        if self._as_of and end_epoch > as_of_epoch:
            end_epoch = as_of_epoch
            clamped = True
        if start_epoch >= end_epoch:
            start_epoch = end_epoch - 30 * 86400
            clamped = True
        resp = httpx.get(
            f"{url}/stock/candles/{kwargs['symbol'].upper()}",
            params={
                "from": start_epoch,
                "to": end_epoch,
                "interval": kwargs.get("interval", "1d"),
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = resp.json()
        if clamped and isinstance(out, dict):
            out["clamped_end_to_as_of"] = True
        return json.dumps(out)
