import json
import time
from datetime import datetime, timezone
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


def _iso_to_epoch(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp())


class CorrelationTool(BaseTool):
    name = "get_correlation"
    description = "Compute news-price correlation analysis for a symbol"
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "End date YYYY-MM-DD"},
        },
        "required": ["symbol", "start_date", "end_date"],
    }
    is_readonly = True
    _as_of: str | None = None

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx
        url = self._services_config.get("vinu_initial_analysis", "http://localhost:8083")
        start_epoch = _date_to_epoch(kwargs["start_date"])
        end_epoch = _date_to_epoch(kwargs["end_date"])
        clamped = False
        if self._as_of:
            as_of_epoch = _iso_to_epoch(self._as_of)
            if end_epoch > as_of_epoch:
                end_epoch = as_of_epoch
                clamped = True
        resp = httpx.get(
            f"{url}/analysis/correlation/{kwargs['symbol'].upper()}",
            params={"from_ts": start_epoch, "to_ts": end_epoch},
            timeout=60,
        )
        resp.raise_for_status()
        out = resp.json()
        if clamped and isinstance(out, dict):
            out["clamped_end_to_as_of"] = True
        return json.dumps(out)
