"""Merge gates for cosine clustering — ticker and entity overlap."""

from __future__ import annotations

from typing import Any

from vinu_news.analysis.post_enrichment.cosine_dedup.settings import (
    REQUIRE_TICKER_OR_ENTITY_OVERLAP,
)
from vinu_news.analysis.storage.models import EnrichedArticle

_CONFLICT_TOKEN_PAIRS = (
    ("earnings_beat", "earnings_miss"),
    ("revenue_beat", "revenue_miss"),
    ("eps_beat", "eps_miss"),
)


def _primary_ticker(item: EnrichedArticle) -> str | None:
    for mention in item.mentions:
        if mention.is_primary:
            return mention.ticker
    if item.mentions:
        return item.mentions[0].ticker
    tickers = item.article.tickers_list()
    return tickers[0] if tickers else None


def _entity_keys(entities: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for person in entities.get("people", []):
        keys.add(f"person:{person.lower()}")
    for country in entities.get("countries", []):
        keys.add(f"country:{country.upper()}")
    return keys


def _has_polarity_conflict(text_a: str, text_b: str) -> bool:
    tokens_a = set(text_a.split())
    tokens_b = set(text_b.split())
    for left, right in _CONFLICT_TOKEN_PAIRS:
        if (left in tokens_a and right in tokens_b) or (
            right in tokens_a and left in tokens_b
        ):
            return True
    return False


def should_merge(
    a: EnrichedArticle,
    b: EnrichedArticle,
    entities_a: dict[str, Any],
    entities_b: dict[str, Any],
) -> bool:
    """Return True if articles share ticker or entity overlap."""
    if _has_polarity_conflict(a.norm_text, b.norm_text):
        return False

    if not REQUIRE_TICKER_OR_ENTITY_OVERLAP:
        return True

    ticker_a = _primary_ticker(a)
    ticker_b = _primary_ticker(b)
    keys_a = _entity_keys(entities_a)
    keys_b = _entity_keys(entities_b)

    if not ticker_a and not ticker_b and not keys_a and not keys_b:
        return True

    if ticker_a and ticker_b and ticker_a == ticker_b:
        return True

    overlap = keys_a & keys_b
    return len(overlap) > 0
