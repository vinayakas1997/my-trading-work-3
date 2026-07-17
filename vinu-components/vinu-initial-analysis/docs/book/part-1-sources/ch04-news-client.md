# Chapter 04 — News API client

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/clients/news_client.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch03 |

## 1. File map

| Method | Endpoint | Description |
|--------|----------|-------------|
| `get_articles_since(ts, until_ts, limit)` | `GET /articles/since` | Fetch articles by timestamp range |
| `get_ticker_news(symbol, days, limit)` | `GET /ticker/{symbol}` | Fetch articles for a specific ticker |

## 2. Data contract

Each article returned contains:

| Field | Type | Example |
|-------|------|---------|
| `id` | str | `"abc123"` |
| `sort_ts` | int | `1712345678` |
| `headline` | str | `"AAPL beats earnings"` |
| `sentiment` | str | `"BULLISH"` |
| `sentiment_score` | int | `75` |
| `impact_label` | str | `"high_bullish"` |
| `tickers` | list | `["AAPL", "MSFT"]` |
| `thread_id` | str | `"thread_xyz"` |

## 3. Logic

The client wraps `net.request()` — a thin wrapper around `requests` with automatic Docker fallback (if running in a container, `127.0.0.1` is transparently rewritten to `host.docker.internal`).

## 4. Tests

| Test file | What it tests |
|-----------|---------------|
| (tested via integration in `test_api.py`) | |
