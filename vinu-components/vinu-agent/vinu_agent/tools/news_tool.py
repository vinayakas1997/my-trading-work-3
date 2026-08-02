import json
import time
from datetime import datetime, timezone
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


def _iso_to_epoch(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp())


class NewsTool(BaseTool):
    name = "get_news"
    description = "Fetch news articles for a symbol over a date range"
    parameters = {
        "symbol": {"type": "string", "description": "Stock symbol"},
        "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        "limit": {"type": "integer", "description": "Max articles to return (default: 20)"},
    }
    is_readonly = True
    _as_of: str | None = None

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_news", "http://localhost:8080")
        to_epoch = _date_to_epoch(kwargs.get("end_date", "")) if kwargs.get("end_date") else None
        clamped = False
        if to_epoch is None:
            to_epoch = int(time.time())
        if self._as_of:
            as_of_epoch = _iso_to_epoch(self._as_of)
            if to_epoch > as_of_epoch:
                to_epoch = as_of_epoch
                clamped = True
        from_epoch = _date_to_epoch(kwargs.get("start_date", "")) if kwargs.get("start_date") else None
        params = {
            "limit": kwargs.get("limit", 20),
        }
        if from_epoch is not None:
            params["from"] = from_epoch
        params["to"] = to_epoch
        resp = httpx.get(
            f"{url}/ticker/{kwargs['symbol'].upper()}",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        out = resp.json()
        if clamped and isinstance(out, dict):
            out["clamped_end_to_as_of"] = True
        return json.dumps(out)
