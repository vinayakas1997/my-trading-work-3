"""Read the news service's answer the way the news service really sends it.

vinu-news answers every list route as `{"count": n, "data": [article, ...]}` and gives times as unix seconds
(`published_at`, `sort_ts`). Two agent readers (memory sync and the trade-plan news section) looked for the keys `results` /
`articles` and called `[:10]` on the time, so they saw "no articles" for every ticker and, had they seen articles, would have
crashed on the integer time. Their tests mocked a bare list, a shape the service never sends. This is the one place that
knows the shape.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def news_articles(body: Any) -> list[dict[str, Any]]:
    """The article list from a news response: the service's `{"data": [...]}`, or a bare list. Anything else is empty."""
    if isinstance(body, dict):
        for key in ("data", "results", "articles"):
            rows = body.get(key)
            if isinstance(rows, list):
                return [r for r in rows if isinstance(r, dict)]
        return []
    if isinstance(body, list):
        return [r for r in body if isinstance(r, dict)]
    return []


def article_date(article: dict[str, Any]) -> str:
    """YYYY-MM-DD of an article, from unix seconds or a date string; an em dash when there is none."""
    for key in ("published_at", "sort_ts", "date"):
        value = article.get(key)
        if isinstance(value, bool) or value in (None, ""):
            continue
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).strftime("%Y-%m-%d")
        return str(value)[:10]
    return "—"
