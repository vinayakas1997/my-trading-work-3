# Data Fetching Summary — 4 Tickers

## Stock Price Data (vinu-stock-price)

All 4 tickers backfilled via Alpaca (IEX feed) from **2022-01-03** through **2025-12-31** (archive complete).

| Ticker | First Bar | Last Bar | 2025 Sample (1d) | Status |
|--------|-----------|----------|-------------------|--------|
| AAPL | 2022-01-03 | 2026-01-01 | $250.41 → $243.39 (4 bars) | complete |
| MSFT | 2022-01-03 | 2026-01-01 | $421.60 → $424.50 (4 bars) | complete |
| TSLA | 2022-01-03 | 2026-01-01 | $401.92 → $412.82 (4 bars) | complete |
| NVDA | 2022-01-03 | 2026-01-01 | $134.29 → $144.99 (4 bars) | complete |

**Storage:** 16 Parquet files (4 symbols × 4 years: 2022–2025), ~3.1M 1m bars

## News Data (vinu-news)

Total: **24,776 articles** (matching our 4 tickers across all ticker mentions)

| Ticker | Articles | Date Range | BULLISH | BEARISH | NEUTRAL |
|--------|----------|------------|---------|---------|---------|
| AAPL | 7,484 | 2020-10-07 → 2026-07-16 | 3,351 | 1,526 | 2,607 |
| MSFT | 5,423 | 2019-09-18 → 2026-07-16 | 2,477 | 991 | 1,955 |
| TSLA | 8,499 | 2014-11-07 → 2026-07-16 | 3,302 | 1,815 | 3,382 |
| NVDA | 6,576 | 2021-11-03 → 2026-07-16 | 3,411 | 1,198 | 1,967 |

**Enrichment:** All articles have sentiment, impact (HIGH/MEDIUM/LOW), priority, category (MARKETS/TECH/EARNINGS/GEOPOLITICS/CRYPTO/ECONOMIC/ENERGY/DEFENSE), thread_id, and threat classification.

## Services Verified

| Service | Port | Status | Key Endpoints Tested |
|---------|------|--------|---------------------|
| vinu-news | 8080 | ✅ Running | `/ticker/{symbol}`, `/high-impact`, `/stats/ticker/{symbol}`, `/threads/active`, `/latest` |
| vinu-stock-price | 8081 | ✅ Running | `/candles/{symbol}`, `/catalog`, `/catalog/{symbol}` |
| vinu-correlation | 8083 | ✅ Running | `/correlation/{ticker}`, `/impact/{ticker}`, `/baseline/{ticker}`, `/drawdown/{ticker}`, `/events/{ticker}`, `/story/{ticker}` |

## Key Bug Found

The `/candles/{symbol}` endpoint returns **0 bars** when using the `days` parameter (tried `days=5`), but works correctly when explicit Unix timestamps are provided via `from` and `to`. This is likely a timezone/offset issue in the `days` parameter calculation.
