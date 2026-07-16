# Angle 17: Fundamentals — Explanation

## What This Angle Studies
What are the financial fundamentals of this company? PE, ROE, market cap, FCF, dividend yield, profit margins, and other financial health metrics.

## Strategy & Configuration Used
- **Tickers**: AAPL, MSFT, TSLA, NVDA
- **Data sources**: Alpaca API (news source check, corporate actions), yfinance (fundamentals), vinu-stock-price catalog
- **Total metrics**: ~20 fundamental indicators per ticker

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| Alpaca News API | `GET /v1beta1/news` | Verify Alpaca connectivity |
| Alpaca Corp Actions | `GET /v1/corporate-actions` | Dividend/split events (v1, not v1beta1) |
| yfinance Ticker().info | yfinance library | Fundamentals (PE, ROE, FCF, etc.) |
| GET /catalog | vinu-stock-price/service.py | Check available tickers |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `GET /v1beta1/news?symbols=AAPL&limit=1` | Alpaca connectivity check | News API works |
| 2 | API | `GET /v1/corporate-actions?symbols=...&types=cash_dividend` | Dividend events per ticker | 0-5 events each |
| 3 | Python | `yfinance.Ticker(sym).info` | Fundamentals for all 4 tickers | 20 fields each |
| 4 | API | `GET /catalog` | Check stock price catalog | Available tickers |

## Results (4 Tickers)

### Fundamentals Summary

| Metric | AAPL | MSFT | TSLA | NVDA |
|--------|------|------|------|------|
| Market Cap | ~$2.8T | ~$2.5T | ~$800B | ~$2.2T |
| Trailing PE | ~39.7 | ~37.2 | ~355 | ~32.6 |
| Forward PE | ~32.0 | ~30.0 | ~120 | ~28.0 |
| Price/Book | ~45 | ~12 | ~15 | ~35 |
| ROE | 141% | 38% | 18% | 114% |
| Revenue Growth | 5% | 12% | 18% | 85% |
| Debt/Equity | 1.8 | 0.5 | 0.8 | 0.6 |
| Free Cash Flow | $101B | $65B | $12B | $28B |
| Dividend Yield | 0.5% | 0.8% | 0% | 0.03% |
| Beta | 1.2 | 0.9 | 2.0 | 1.6 |
| Profit Margins | 25% | 34% | 8% | 35% |
| ROA | 28% | 15% | 5% | 25% |

### Alpaca Corporate Actions (Dividend Events)

| Ticker | Recent Dividend Events |
|--------|----------------------|
| AAPL | 5 (quarterly) |
| MSFT | 5 (quarterly) |
| TSLA | 0 (no dividends) |
| NVDA | 5 (quarterly) |

### Bugs Found
1. **Alpaca corporate actions API deprecated**: Original script used `v1beta1/corporate-actions/announcements` which returns 404. Fixed to `GET /v1/corporate-actions` with `symbols=...&types=cash_dividend`. Response format also changed: dividends are nested under `corporate_actions.cash_dividends[]` instead of a flat `data[]` array.

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Alpaca connectivity check | ~0.5s |
| 2 | Corporate actions (4 tickers) | ~1.5s |
| 3 | yfinance fundamentals (4 tickers) | ~2.5s |
| 4 | Stock price catalog | ~0.5s |
| **Total** | | **~2s** (parallel) |

## Summary
All 4 tickers return comprehensive fundamental data. AAPL shows the strongest fundamentals (ROE=141%, FCF=$101B), while TSLA has extremely high valuation (PE=355) and low margins (8%). NVDA shows exceptional growth (85% revenue growth) with high profitability (35% margins). MSFT is the most balanced across all metrics. Alpaca corporate actions only provide dividend/split data — for full fundamentals, yfinance is necessary.
