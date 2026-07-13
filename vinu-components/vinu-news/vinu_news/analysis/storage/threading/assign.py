"""Story thread assignment helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from vinu_news.analysis.storage.models import EnrichedArticle


def generate_thread_id(norm_text: str, sort_ts: int, dominant_ticker: str | None) -> str:
    """Create stable thread id for a new story."""
    key = f"{norm_text}|{dominant_ticker or ''}|{sort_ts}"
    return hashlib.sha256(key.encode()).hexdigest()[:32]


def dominant_ticker_from_mentions(item: EnrichedArticle) -> str | None:
    for mention in item.mentions:
        if mention.is_primary:
            return mention.ticker
    if item.mentions:
        return item.mentions[0].ticker
    tickers = item.article.tickers_list()
    return tickers[0] if tickers else None


def thread_row_from_article(
    item: EnrichedArticle,
    thread_id: str,
) -> dict[str, Any]:
    a = item.article
    return {
        "thread_id": thread_id,
        "first_seen_at": a.sort_ts,
        "last_seen_at": a.sort_ts,
        "article_count": 1,
        "lead_headline": a.headline,
        "dominant_ticker": dominant_ticker_from_mentions(item),
        "entities_json": a.entities_json,
        "category": a.category,
        "last_article_id": a.id,
        "norm_text": item.norm_text,
    }
