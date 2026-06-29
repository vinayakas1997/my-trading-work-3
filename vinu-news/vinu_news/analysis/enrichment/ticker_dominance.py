"""Per-ticker dominance scoring for multi-ticker articles."""

import re

HEADLINE_WEIGHT = 3
SUMMARY_WEIGHT = 1
POSITION_BONUS = 2
POSITION_WINDOW = 40


def _count_ticker(text: str, ticker: str) -> int:
    if not text:
        return 0
    return len(re.findall(rf"\b{re.escape(ticker)}\b", text))


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

    raw_scores: dict[str, float] = {}
    headline_prefix = headline[:POSITION_WINDOW]

    for ticker in tickers:
        score = (
            _count_ticker(headline, ticker) * HEADLINE_WEIGHT
            + _count_ticker(summary, ticker) * SUMMARY_WEIGHT
        )
        if ticker in headline_prefix:
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
