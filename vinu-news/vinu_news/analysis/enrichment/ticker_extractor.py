"""Ticker extraction from headline and summary (Fincept Section 6F)."""

import re

TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")
MAX_TICKERS = 5

TICKER_STOP_WORDS = frozenset({
    "THE", "FOR", "AND", "BUT", "NOT", "FROM", "WITH", "THIS", "THAT",
    "HAVE", "WILL", "BEEN", "THEY", "WERE", "SAID", "HAS", "ITS", "NEW",
    "ARE", "WAS",
    # Extended Python NLP list (Fincept Section 6F)
    "WHO", "HOW", "WHY", "ALL", "CAN", "MAY", "NOW", "SEC", "GDP", "CEO",
    "CFO", "IPO", "ETF", "CPI", "PMI",
})


def extract_tickers(headline: str, summary: str) -> list[str]:
    """Extract up to 5 unique ticker symbols from headline + summary."""
    text = f"{headline} {summary}"
    seen: set[str] = set()
    tickers: list[str] = []

    for match in TICKER_PATTERN.finditer(text):
        candidate = match.group()
        if candidate in TICKER_STOP_WORDS:
            continue
        if candidate not in seen:
            seen.add(candidate)
            tickers.append(candidate)
            if len(tickers) >= MAX_TICKERS:
                break

    return tickers
