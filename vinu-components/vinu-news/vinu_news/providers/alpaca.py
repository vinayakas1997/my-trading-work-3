from __future__ import annotations

import logging
from datetime import datetime, timezone

import requests

from vinu_infra.rate_limit import TokenBucket
from vinu_news import net

LOG = logging.getLogger(__name__)

ALPACA_DATA_BASE_URL = "https://data.alpaca.markets"
TIMEOUT_SEC = 30
MAX_PER_PAGE = 50

_RATE_LIMITER = TokenBucket(rate=200, per=60)


class AlpacaTickerNewsProvider:
    provider_id = "alpaca"

    def __init__(self, api_key: str, api_secret: str):
        self._api_key = api_key
        self._api_secret = api_secret
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_secret)

    def fetch_ticker_news(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
    ) -> list[dict]:
        start_iso = _ts_to_iso(from_ts)
        end_iso = _ts_to_iso(to_ts)
        articles: list[dict] = []
        page_token: str | None = None
        url = f"{ALPACA_DATA_BASE_URL}/v1beta1/news"

        page = 0
        while True:
            page += 1
            params: dict[str, str] = {
                "symbols": ticker.upper(),
                "start": start_iso,
                "end": end_iso,
                "limit": str(MAX_PER_PAGE),
                "include_content": "false",
                "exclude_contentless": "true",
            }
            if page_token:
                params["page_token"] = page_token

            try:
                _RATE_LIMITER.wait()
                resp = net.request("GET", url, headers=self._headers, params=params, timeout=TIMEOUT_SEC)
            except requests.RequestException as exc:
                status = resp.status_code if hasattr(resp, 'status_code') else 'N/A'
                body = resp.text[:200] if hasattr(resp, 'text') else 'N/A'
                LOG.warning(
                    "Alpaca news fetch failed for %s (page %d, range %s to %s): "
                    "HTTP %s, body=%s, error=%s",
                    ticker, page, start_iso, end_iso, status, body, exc,
                )
                break

            data = resp.json()
            chunk = data.get("news", [])
            articles.extend(_map_article(a, ticker) for a in chunk)

            page_token = data.get("next_page_token")
            if not page_token:
                break

        LOG.info(
            "Alpaca news fetched %d articles for %s in %d pages (%s to %s)",
            len(articles), ticker, page, start_iso, end_iso,
        )

        return articles


def _ts_to_iso(ts: int) -> str:
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _map_article(raw: dict, ticker: str) -> dict:
    ts = _parse_alpaca_ts(raw.get("created_at", ""))
    symbols = [
        s if isinstance(s, str) else s.get("symbol", "")
        for s in raw.get("symbols", [])
    ]
    symbols = [s for s in symbols if s]
    if not symbols:
        symbols = [ticker]

    return {
        "headline": (raw.get("headline") or "").strip(),
        "summary": (raw.get("summary") or "").strip(),
        "link": (raw.get("url") or "").strip(),
        "pubDate": raw.get("created_at", ""),
        "source": (raw.get("source") or "ALPACA").strip().upper(),
        "region": "US",
        "tier": 2,
        "category": "MARKETS",
        "ticker": ticker,
    }


def _parse_alpaca_ts(iso_str: str) -> int:
    if not iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return 0
