# Chapter 16 — Arrow schemas & models

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/storage/models.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch15 |

## 1. Problem

Three distinct data types are stored as Parquet tables, each requiring a well-defined Arrow schema for type safety and consistency.

## 2. Schemas

### Impact events (`IMPACT_SCHEMA`)

| Field | Type | Description |
|-------|------|-------------|
| `article_id` | string | Unique article identifier |
| `symbol` | string | Ticker symbol |
| `is_primary` | bool | Primary vs secondary ticker |
| `ticker_count` | int64 | Total tickers in the article |
| `ts` | int64 | Article timestamp |
| `session` | string | Market session name |
| `headline` | string | Article headline |
| `sentiment` | string | BULLISH/BEARISH/NEUTRAL |
| `sentiment_score` | int64 | Numerical sentiment (0–100) |
| `impact_label` | string | high_bearish/high_bullish/medium/low |
| `price_change_5m` | float64 | Price change in 5m window |
| `price_change_15m` | float64 | Price change in 15m window |
| `price_change_30m` | float64 | Price change in 30m window |
| `price_change_1h` | float64 | Price change in 1h window |
| `price_change_1d` | float64 | Price change in 1d window |
| `abnormal_return_30m` | float64 | Abnormal return |
| `car_1h` | float64 | Cumulative abnormal return |
| `ar_p_value` | float64 | Event study p-value |
| `ar_significant` | bool | Significance flag |
| `thread_id` | string | Story thread ID |
| `computed_at` | int64 | When the event was computed |

### Baseline snapshots (`BASELINE_SCHEMA`)

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Ticker symbol |
| `hour_ts` | int64 | Hour bucket timestamp |
| `session` | string | Market session |
| `article_count` | int64 | Articles in this hour |
| `mean` | float64 | Rolling mean |
| `stddev` | float64 | Rolling stddev |
| `sample_size` | int64 | Window sample count |

### Correlation matrices (`CORRELATION_SCHEMA`)

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | string | Ticker symbol |
| `window` | string | Time window label |
| `period_start` | int64 | Period start timestamp |
| `period_end` | int64 | Period end timestamp |
| `sample_size` | int64 | Number of hourly observations |
| `news_return_corr` | float64 | Pearson correlation |
| `corr_p_value` | float64 | Correlation p-value |
| `corr_ci_lower` | float64 | Bootstrap CI lower |
| `corr_ci_upper` | float64 | Bootstrap CI upper |
| `granger_p_value` | float64 | Granger test p-value |
| `granger_best_lag_mins` | int64 | Best Granger lag |
| `sentiment_return_corr` | float64 | Sentiment vs return r |
| `news_volume_corr` | float64 | News volume vs abs(return) r |
