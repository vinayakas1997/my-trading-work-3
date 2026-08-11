import json
import time
from ..agent.tools import BaseTool


def _date_to_epoch(date_str: str) -> int:
    return int(time.mktime(time.strptime(date_str, "%Y-%m-%d")))


class FeaturesTool(BaseTool):
    name = "get_features"
    description = (
        "Compute technical indicators for a symbol over a date range, from vinu-tools' real "
        "catalog (24 indicators, not just SMA/RSI/MACD -- call list_available_features first "
        "to see the real, current list rather than guessing names). Pass EITHER `indicators` "
        "(specific ones) OR `preset` (a named bundle, e.g. alpha101_benchmark for WorldQuant's "
        "101 alphas, or full_ta for all 32) -- not both."
    )
    parameters = {
        "type": "object",
        "properties": {
            "symbol": {"type": "string", "description": "Stock symbol"},
            "indicators": {
                "type": "string",
                "description": "Comma-separated indicator names from list_available_features (e.g., sma_20,rsi_14,macd). Omit if using preset.",
            },
            "preset": {
                "type": "string",
                "description": "A named preset bundle from list_available_features (e.g. full_ta, alpha101_benchmark). Omit if using indicators.",
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
        symbol = kwargs["symbol"].upper()
        preset = kwargs.get("preset", "").strip()
        from_ts = _date_to_epoch(kwargs["start_date"])
        to_ts = _date_to_epoch(kwargs["end_date"])
        title = f"agent_{symbol}_{from_ts}_{to_ts}"
        payload = {
            "title": title,
            "symbols": [symbol],
            "from_ts": from_ts,
            "to_ts": to_ts,
            "run_immediately": True,
        }
        if preset:
            payload["preset"] = preset
        else:
            indicators = [
                i.strip()
                for i in kwargs.get("indicators", "sma_20,rsi_14").split(",")
                if i.strip()
            ]
            payload["features"] = indicators
        resp = httpx.post(
            f"{url}/features/requests",
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        created = resp.json()
        request_id = created.get("id")
        if created.get("status") != "done" or request_id is None:
            return json.dumps(
                {"status": "error", "tool": "get_features", "request": created}
            )
        data_resp = httpx.get(
            f"{url}/features/requests/{request_id}/data",
            timeout=60,
        )
        data_resp.raise_for_status()
        return data_resp.text
