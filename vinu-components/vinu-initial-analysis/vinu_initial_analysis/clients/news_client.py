from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)


class NewsClient:
    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/")

    def get_articles_since(self, ts: int, until_ts: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"ts": ts, "limit": limit}
        if until_ts is not None:
            params["until_ts"] = until_ts
        resp = request("GET", f"{self._base}/articles/since", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body

    def get_ticker_news(
        self,
        symbol: str,
        days: int = 7,
        *,
        from_ts: int | None = None,
        to_ts: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        import time

        params: dict[str, Any] = {"limit": limit}
        if from_ts is not None:
            params["from"] = from_ts
            params["to"] = to_ts if to_ts is not None else int(time.time())
        else:
            params["days"] = days
        resp = request("GET", f"{self._base}/ticker/{symbol.upper()}", params=params)
        resp.raise_for_status()
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body
