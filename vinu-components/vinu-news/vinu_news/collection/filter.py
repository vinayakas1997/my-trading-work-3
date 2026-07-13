"""Ticker-mode persist filter."""

from __future__ import annotations

from vinu_news.analysis.storage.models import EnrichedArticle


def filter_leads_for_mode(
    leads: list[EnrichedArticle],
    mode: str,
    watchlist: set[str],
) -> list[EnrichedArticle]:
    """Return leads to persist based on collection mode."""
    if mode != "ticker":
        return leads
    if not watchlist:
        return []
    upper = {t.upper() for t in watchlist}
    filtered: list[EnrichedArticle] = []
    for item in leads:
        mention_tickers = {m.ticker.upper() for m in item.mentions}
        article_tickers = {t.upper() for t in item.article.tickers_list()}
        if upper & mention_tickers or upper & article_tickers:
            filtered.append(item)
    return filtered


def article_matches_watchlist(item: EnrichedArticle, watchlist: set[str]) -> bool:
    """True if article mentions any watchlist ticker."""
    if not watchlist:
        return False
    upper = {t.upper() for t in watchlist}
    mention_tickers = {m.ticker.upper() for m in item.mentions}
    article_tickers = {t.upper() for t in item.article.tickers_list()}
    return bool(upper & mention_tickers or upper & article_tickers)
