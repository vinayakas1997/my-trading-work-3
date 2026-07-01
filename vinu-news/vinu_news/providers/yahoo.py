"""Yahoo Finance ticker headline RSS (TASK-N02)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

LOG = logging.getLogger(__name__)
USER_AGENT = "vinu-news/1.0"
TIMEOUT_SEC = 10


class YahooTickerNewsProvider:
    provider_id = "yahoo"

    def is_configured(self) -> bool:
        return True

    def fetch_ticker_news(
        self,
        ticker: str,
        from_ts: int,
        to_ts: int,
    ) -> list[dict]:
        sym = ticker.strip().upper()
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym}&region=US&lang=en-US"
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT_SEC)
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
        except requests.RequestException as exc:
            LOG.warning("Yahoo ticker news fetch failed for %s: %s", sym, exc)
            return []

        articles: list[dict] = []
        for entry in parsed.entries:
            headline = str(getattr(entry, "title", "") or "").strip()
            link = str(getattr(entry, "link", "") or "").strip()
            if not headline or not link:
                continue
            pub_raw = getattr(entry, "published", None) or getattr(entry, "updated", None)
            pub_date = str(pub_raw) if pub_raw else ""
            sort_ts = _parse_pub_ts(pub_date)
            if sort_ts and (sort_ts < from_ts or sort_ts > to_ts):
                continue
            summary = str(getattr(entry, "summary", "") or "")
            articles.append(
                {
                    "headline": headline,
                    "summary": summary,
                    "link": link,
                    "pubDate": pub_date,
                    "source": f"YAHOO {sym}",
                    "region": "US",
                    "tier": 2,
                    "category": "MARKETS",
                }
            )
        return articles


def _parse_pub_ts(pub_date: str) -> int | None:
    if not pub_date:
        return None
    try:
        dt = parsedate_to_datetime(pub_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        return None
