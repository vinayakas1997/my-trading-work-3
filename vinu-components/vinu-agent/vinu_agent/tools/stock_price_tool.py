import json
import time
from ..agent.tools import BaseTool
from ._call_cache import CallCache
from ._date_utils import date_to_epoch as _date_to_epoch
from ._date_utils import iso_to_epoch as _iso_to_epoch


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
        self._cache = CallCache()

    def execute(self, **kwargs) -> str:
        import httpx
        try:
            from vinu_infra.auth import internal_auth_headers as _iah
            _h = _iah() or None
        except Exception:
            _h = None
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

        symbol = kwargs["symbol"].upper()
        interval = kwargs.get("interval", "1d")
        # item #11 finding #4: keyed on the FINAL, post-clamp params, not
        # the raw kwargs -- two calls that phrase their date range
        # differently but clamp down to the identical window must still
        # hit the same cache entry.
        cache_key = (symbol, start_epoch, end_epoch, interval, clamped)
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        resp = httpx.get(
            f"{url}/stock/candles/{symbol}",
            headers=_h,
            params={
                "from": start_epoch,
                "to": end_epoch,
                "interval": interval,
            },
            timeout=30,
        )
        resp.raise_for_status()
        out = resp.json()
        if clamped and isinstance(out, dict):
            out["clamped_end_to_as_of"] = True
        result = json.dumps(out)
        self._cache.set(cache_key, result)
        return result
