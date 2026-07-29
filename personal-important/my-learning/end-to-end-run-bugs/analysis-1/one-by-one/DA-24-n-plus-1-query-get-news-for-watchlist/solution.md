# DA-24 🟡 N+1 Query in `get_news_for_watchlist`

**Component:** `vinu-news`
**Files Changed:** `sqlite_backend.py`

## Problem

`get_news_for_watchlist()` called `get_news_for_ticker()` in a loop — one SQL query per watchlist ticker. For a 10-ticker watchlist, that's 10 separate queries.

```python
# BEFORE — N+1 queries
per_ticker = max(1, limit // len(tickers))
for symbol in tickers:
    rows = self.get_news_for_ticker(symbol, start_ts, None, per_ticker)
```

## Root Cause

The method iterated over each ticker and called a single-ticker query, then deduplicated and sorted the results in Python.

## Solution

Replaced the N+1 loop with a single SQL query using `IN (?, ?, ...)`:

```python
placeholders = ", ".join("?" for _ in tickers)
query = f"""
    SELECT a.*, m.ticker AS mention_ticker, m.dominance, m.is_primary, n.analysis_json AS llm_analysis
    FROM article_ticker_mentions m
    JOIN articles a ON a.id = m.article_id
    LEFT JOIN news_analysis n ON a.link = n.url
    WHERE m.ticker IN ({placeholders})
"""
params = [t.upper() for t in tickers]
if start_ts is not None:
    query += " AND a.sort_ts >= ?"
    params.append(start_ts)
query += " ORDER BY a.sort_ts DESC LIMIT ?"
params.append(limit)
```

Deduplication by `article_id` preserved in Python after the query.

## Trade-off

- **Before:** Per-ticker limit (each ticker guaranteed ≥1 article)
- **After:** Global LIMIT (top N articles across all tickers)
- For the typical use case (watchlist news API), callers want the most recent articles overall — this is acceptable

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `sqlite_backend.py:191-211` | 20 → 19 | Replaced N+1 loop with single `IN` query; preserved dedup + sort |

## Verification

Manual validation with 5 test cases passes (all articles, limit, start_ts filter, dedup across ticker mentions, empty tickers).
