# Gap: ticker-relevant articles get dropped by name-vs-symbol filtering

## Summary

Even when a ticker (e.g. `AAPL`) is in the watchlist and mode is `"ticker"`, most
genuinely relevant articles about that company are silently discarded before
they reach the database — including ones fetched by a source built specifically
to return AAPL-only news. The cause is that ticker matching is done with a
plain regex looking for the literal uppercase symbol in the text, with no
company-name-to-ticker mapping anywhere in the pipeline.

## Where the filter lives

`filter_leads_for_mode()` in
[`vinu_news/collection/filter.py`](../vinu_news/collection/filter.py):

```python
def filter_leads_for_mode(leads, mode, watchlist):
    if mode != "ticker":
        return leads
    if not watchlist:
        return []
    upper = {t.upper() for t in watchlist}
    filtered = []
    for item in leads:
        mention_tickers = {m.ticker.upper() for m in item.mentions}
        article_tickers = {t.upper() for t in item.article.tickers_list()}
        if upper & mention_tickers or upper & article_tickers:
            filtered.append(item)
    return filtered
```

`mentions` / `tickers_list()` both trace back to
[`extract_tickers()`](../vinu_news/analysis/enrichment/ticker_extractor.py):

```python
TICKER_PATTERN = re.compile(r"\b[A-Z]{2,5}\b")

def extract_tickers(headline: str, summary: str) -> list[str]:
    text = f"{headline} {summary}"
    ...  # regex-matches 2-5 letter uppercase tokens, minus a stop-word list
```

There is **no** company-name → ticker alias table anywhere in the codebase
("Apple" → `AAPL`, "Google"/"Alphabet" → `GOOGL`, etc.). Confirmed by
grepping the whole `vinu_news/` tree — zero hits for any such mapping. The
NER step (`analysis/post_enrichment/ner/`) only resolves **countries** and
**people**, not companies.

This filter runs on articles from **both** paths:

- RSS feeds (`run_ingestion_cycle`, `feeds.yaml`, ~22 general sources)
- The dedicated per-ticker fetch (`run_ticker_news_ingest` →
  `TickerNewsRegistry` → Yahoo/FMP), at
  [`service.py:335`](../vinu_news/service.py)

The RSS case is expected to lose most matches — general feeds rarely spell
out the ticker symbol. The costly case is the **second** one: Yahoo's
per-ticker feed is *already* filtered server-side to be about that ticker,
and we throw most of it away anyway by re-checking with the same
company-name-blind regex.

## Measured impact (live test, 2026-07-01)

With `AAPL` and `GOOGL` in the watchlist, querying
`TickerNewsRegistry.fetch_for_ticker()` directly and running each raw item
through `extract_tickers()`:

| Ticker | Raw headlines from Yahoo | Passed filter | Dropped |
|--------|--------------------------|----------------|---------|
| AAPL   | 20                       | 4              | 16      |
| GOOGL  | 20                       | 1              | 19      |

Examples of headlines Yahoo fetched *specifically because they're about
AAPL/GOOGL*, dropped anyway because the symbol never appears as literal
uppercase text:

- "Apple Warned by Russia Over Local Apps" — dropped (`extract_tickers` → `[]`)
- "Trump Disclosure Puts Nvidia and Apple in Focus" — dropped
- "Micron and Apple Trade Blame as Prices Soar on Laptops, Phones, and More" — dropped
- "Google's AI Coding Push Faces Talent Drain" — dropped

Headlines that happened to spell out the symbol (e.g. "AAPL Stock Slides
After-Hours...", or a summary containing "(NASDAQ:AAPL)") passed. That's the
only thing distinguishing kept vs. dropped — not relevance, not source
confidence, just whether the raw text happened to contain the ticker
symbol as an uppercase token.

This is also why re-polling the same watchlist repeatedly during testing
appeared to "stop growing" at 7 saved articles: dozens of new, genuinely
relevant candidates were being fetched every cycle, but ~87% of them never
survived the filter, cycle after cycle.

## Why this matters

- Yahoo/FMP are meant to be the *dedicated, high-confidence* path for a
  ticker. Re-running a blunt company-name-blind regex against their output
  defeats the purpose of a dedicated fetch — the source has already done
  the hard part.
- For RSS, this is a smaller, expected loss (general feeds rarely use bare
  symbols). For the dedicated ticker path, this is a large, avoidable loss.

## Possible fixes (not yet implemented, for future work)

1. **Skip the mode filter for dedicated ticker-news results.** Since
   `run_ticker_news_ingest` already queries per-symbol, its output doesn't
   need to be re-verified by `filter_leads_for_mode` — every article it
   returns is already about that ticker by construction.
2. **Add a company-name → ticker alias table** (e.g. "Apple"/"Apple Inc." →
   `AAPL`, "Google"/"Alphabet" → `GOOGL`) and match against it in
   `extract_tickers`, so RSS articles that use the company name instead of
   the symbol are no longer invisible to the filter.
3. Combine both: alias table for RSS-sourced text, and a bypass for
   provider-sourced (Yahoo/FMP) results.

No code changes have been made for this yet — this doc is a record of the
gap for future work.
