"""Build per-ticker mention rows from enriched article + dominance map."""

import hashlib

from vinu_news.analysis.storage.models import TickerMention
from vinu_news.analysis.enrichment.ticker_dominance import primary_ticker


def _mention_id(article_id: str, ticker: str) -> str:
    raw = f"{article_id}:{ticker}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def build_ticker_mentions(
    article_id: str,
    dominance: dict[str, float],
) -> list[TickerMention]:
    """Create junction-table rows for each ticker in an article."""
    if not dominance:
        return []

    primary = primary_ticker(dominance)
    mentions: list[TickerMention] = []

    for ticker, score in dominance.items():
        mentions.append(
            TickerMention(
                id=_mention_id(article_id, ticker),
                article_id=article_id,
                ticker=ticker,
                dominance=round(score, 4),
                is_primary=1 if ticker == primary else 0,
            )
        )

    return mentions


def split_co_tickers(
    ticker: str,
    dominance: dict[str, float],
) -> dict[str, float]:
    """Return co-ticker dominance map excluding the primary ticker key."""
    return {t: v for t, v in dominance.items() if t != ticker}
