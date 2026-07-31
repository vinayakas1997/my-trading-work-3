from __future__ import annotations

import logging
from typing import Any

from vinu_initial_analysis.net import request

LOG = logging.getLogger(__name__)


class NewsClient:
    _PREFIX = "/news"
    _PAGE_LIMIT = 500

    def __init__(self, base_url: str):
        self._base = base_url.rstrip("/").removesuffix("/news") + self._PREFIX

    @staticmethod
    def _extract(resp) -> list[dict[str, Any]]:
        body = resp.json()
        return body.get("data", body) if isinstance(body, dict) else body

    def get_articles_since(self, ts: int, until_ts: int | None = None, limit: int = 500) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"ts": ts, "limit": min(limit, self._PAGE_LIMIT)}
        if until_ts is not None:
            params["until_ts"] = until_ts
        resp = request("GET", f"{self._base}/articles/since", params=params)
        resp.raise_for_status()
        return self._extract(resp)

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

        page_size = min(limit, self._PAGE_LIMIT)
        if from_ts is None:
            params: dict[str, Any] = {"limit": page_size, "days": days}
            resp = request("GET", f"{self._base}/ticker/{symbol.upper()}", params=params)
            resp.raise_for_status()
            return self._extract(resp)

        # Keyset-paginate the whole [from_ts, to_ts] window: the news API
        # returns at most 500 rows per request ordered by sort_ts DESC with
        # no offset, so single-shot fetches silently truncate to the most
        # recent page (Bug-4). Slide `to` backward past the oldest article
        # of each page until the window is exhausted.
        collected: list[dict[str, Any]] = []
        seen: set = set()
        to = to_ts if to_ts is not None else int(time.time())
        while True:
            params = {"limit": page_size, "from": from_ts, "to": to}
            resp = request("GET", f"{self._base}/ticker/{symbol.upper()}", params=params)
            resp.raise_for_status()
            batch = self._extract(resp)
            if not batch:
                break
            earliest = None
            for article in batch:
                a_ts = article.get("sort_ts", article.get("ts"))
                if a_ts is not None:
                    earliest = a_ts if earliest is None else min(earliest, a_ts)
                dedup_key = article.get("id") or article.get("link") or article.get("url") or a_ts
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)
                collected.append(article)
            if len(batch) < page_size or earliest is None or earliest <= from_ts:
                break
            to = earliest - 1
        return collected
