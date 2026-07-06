# Chapter 08 — Correlation metrics

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/engine/correlation.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch07 |

## 1. Problem

Quantify the relationship between news activity and price returns using Pearson correlation with bootstrap confidence intervals.

## 2. Metrics produced

| Metric | Description |
|--------|-------------|
| `news_return_corr` | Pearson r between hourly article count and hourly return |
| `corr_p_value` | P-value of the Pearson test |
| `corr_ci_lower` | 95% bootstrap CI lower bound |
| `corr_ci_upper` | 95% bootstrap CI upper bound |
| `sentiment_return_corr` | Pearson r between avg sentiment score and return |
| `news_volume_corr` | Pearson r between article count and abs(return) |

## 3. Preprocessing

### News resampling

Articles are bucketed into 1-hour windows by `sort_ts`:

| Field | Aggregation |
|-------|-------------|
| `article_count` | Count per hour |
| `avg_sentiment` | Mean per hour |
| `avg_impact` | Mean impact score per hour |

### Returns resampling

Candles are bucketed into 1-hour windows. Return is calculated as `(close - open) / open * 100`.

## 4. Bootstrap CI

Uses `scipy.stats.bootstrap` with 1000 resamples and the percentile method at 95% confidence. Falls back to the point estimate if bootstrapping fails.

## 5. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_correlation.py` | Resampling, correlation computation, edge cases |
