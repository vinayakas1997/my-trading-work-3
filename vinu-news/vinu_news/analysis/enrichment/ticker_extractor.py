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


def extract_tickers(
    headline: str,
    summary: str,
    watchlist: set[str] | None = None,
) -> list[str]:
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

    if len(tickers) < MAX_TICKERS:
        # Resolve company names to tickers via alias database.
        # Look up both: already-extracted tickers and watchlist tickers.
        lookup_tickers = set(tickers)
        if watchlist:
            lookup_tickers.update(t.upper() for t in watchlist)

        if lookup_tickers:
            from vinu_news.analysis.enrichment.ticker_db import get_mappings_for_tickers
            alias_to_ticker, _ = get_mappings_for_tickers(lookup_tickers)
            if alias_to_ticker:
                text_upper = text.upper()
                sorted_aliases = sorted(alias_to_ticker.keys(), key=len, reverse=True)
                for alias in sorted_aliases:
                    ticker = alias_to_ticker[alias]
                    if ticker in seen:
                        continue
                    if re.search(rf"\b{re.escape(alias.upper())}\b", text_upper):
                        seen.add(ticker)
                        tickers.append(ticker)
                        if len(tickers) >= MAX_TICKERS:
                            break

    return tickers
