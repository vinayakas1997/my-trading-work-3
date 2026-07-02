"""Per-ticker dominance scoring for multi-ticker articles."""

import re
from vinu_news.analysis.enrichment.ticker_db import get_mappings_for_tickers

HEADLINE_WEIGHT = 3
SUMMARY_WEIGHT = 1
POSITION_BONUS = 2
POSITION_WINDOW = 40


def _count_ticker(text: str, ticker: str, ticker_to_aliases: dict[str, list[str]]) -> int:
    if not text:
        return 0
    text_upper = text.upper()
    ticker_upper = ticker.upper()
    count = len(re.findall(rf"\b{re.escape(ticker_upper)}\b", text_upper))
    # Count aliases
    for alias in ticker_to_aliases.get(ticker_upper, []):
        count += len(re.findall(rf"\b{re.escape(alias)}\b", text_upper))
    return count


def compute_dominance(
    tickers: list[str],
    headline: str,
    summary: str,
) -> dict[str, float]:
    """
    Score each ticker's relative dominance in an article.
    Returns normalized weights summing to 1.0 across all tickers.
    """
    if not tickers:
        return {}

    _, ticker_to_aliases = get_mappings_for_tickers(set(tickers))
    raw_scores: dict[str, float] = {}
    headline_prefix = headline[:POSITION_WINDOW]
    prefix_upper = headline_prefix.upper()

    for ticker in tickers:
        score = (
            _count_ticker(headline, ticker, ticker_to_aliases) * HEADLINE_WEIGHT
            + _count_ticker(summary, ticker, ticker_to_aliases) * SUMMARY_WEIGHT
        )
        ticker_upper = ticker.upper()
        if ticker_upper in prefix_upper or any(
            alias in prefix_upper for alias in ticker_to_aliases.get(ticker_upper, [])
        ):
            score += POSITION_BONUS
        raw_scores[ticker] = max(score, 0.0)

    total = sum(raw_scores.values())
    if total == 0:
        equal = 1.0 / len(tickers)
        return {t: equal for t in tickers}

    return {t: raw_scores[t] / total for t in tickers}


def primary_ticker(dominance: dict[str, float]) -> str | None:
    """Return ticker with highest dominance, or None if empty."""
    if not dominance:
        return None
    return max(dominance, key=dominance.get)  # type: ignore[arg-type]
