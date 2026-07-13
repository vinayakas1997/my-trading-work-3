"""In-batch URL deduplication."""

from __future__ import annotations

import logging
from typing import Any

from vinu_news.analysis.storage.repository import normalize_link

logger = logging.getLogger(__name__)


def dedup_urls_batch(raw_articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate links within a poll batch (first occurrence wins)."""
    seen: set[str] = set()
    kept: list[dict[str, Any]] = []
    for article in raw_articles:
        link = article.get("link", "")
        key = normalize_link(link) if link else ""
        if key and key in seen:
            logger.debug("URL dedup dropped duplicate link: %s", link)
            continue
        if key:
            seen.add(key)
        kept.append(article)
    return kept
