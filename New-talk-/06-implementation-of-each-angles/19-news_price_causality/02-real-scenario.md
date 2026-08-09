---
name: news_price_causality-real-scenario
status: phase-1-done
purpose: one concrete, real example proving news_price_causality's two-granularity backtest actually works, and the real measured Granger/correlation result on the one real quarter with enough data.
---

# 19 — news_price_causality — Real Scenario

156 real AAPL-linked articles (vinu-news's cached `news.db`, 2023-01-01 to
2023-01-30 — the entire real cached window) + real AAPL 1-minute bars
(Alpaca, ±7 days padding, from the 2023 archive).

## The calls

```python
from vinu_initial_analysis.angles.news_price_causality.backtest import (
    run_impact_backtest, run_aggregate_tests_backtest,
)

impact_df = run_impact_backtest("AAPL", candles, articles)       # 268 rows, 0.35s
agg_df = run_aggregate_tests_backtest("AAPL", candles, articles)  # 3 rows, 0.56s
```

## Real output — one AAPL impact row

```json
{
  "type": "impact", "symbol": "AAPL", "is_primary": true, "ticker_count": 1,
  "ts": 1672756124, "session": "ny", "subsession": "premarket",
  "day_of_week": "tuesday", "week_of_month": 1, "month": 1, "quarter": 1,
  "headline": "Apple Hikes Battery Replacement Service Fee For Out-Of-Warranty iPhones, iPads, And MacBooks",
  "sentiment": "NEUTRAL", "sentiment_score": 0, "impact_label": "low",
  "price_change_5m": -0.4835, "price_change_30m": -0.4835, "price_change_1d": -0.4835,
  "ar_model": "none", "ar_significant": false,
  "novelty_score": 0.986
}
```

Of the 156 AAPL-specific rows, 52 got a real `mean_adjusted` abnormal-
return model (no `price_client` was passed for this check, so SPY's
market-model path wasn't exercised here — a legitimate, explicitly-
labeled degradation), 4 came back `ar_significant: true`.

## Real output — the one quarter with enough data

```json
[
  {"type": "granger", "quarter_key": "2023-Q1", "granger_causes_prices": false,
   "best_lag_minutes": 720, "p_value": 0.279, "sample_size": 43},
  {"type": "correlation", "quarter_key": "2023-Q1", "news_return_corr": -0.1996,
   "corr_p_value": 0.199, "sentiment_return_corr": -0.0077, "sample_size": 43},
  {"type": "lag", "quarter_key": "2023-Q1", "best_lag_minutes": 0,
   "best_lag_correlation": -0.1996}
]
```

**Originally**: no `significance_model_eval` row — every one of the 156
real articles had `finbert_score: NULL` (confirmed directly: `SELECT
COUNT(*), COUNT(finbert_score) FROM articles` → `(156, 0)`), and the
classifier's leak-safety code required `finbert_score` as a non-optional
feature, so `usable` ended up empty and the function correctly returned
no scores — the documented "not enough data" path, not a new failure.
Tracked in `known-issues.md`.

**After the fix** (`known-issues.md` Resolved #4 — real `finbert_score`
backfilled for all 156 articles via the FinBERT model): `usable` now
clears its 130-row floor (268/268 real rows have complete features), but
`score_significance` *still* returns no eval row — this real dataset only
has 5 real `ar_significant: true` examples total (need 10 train + 3
test), a genuine, separate data-scarcity limit distinct from the
finbert_score bug. Confirmed directly:

```python
usable = 268   # was 0 before the fix; floor is 130
y_train positives = 3   # need >= 10
y_test positives  = 2   # need >= 3
total ar_significant=True in the real sample = 5
```

The finbert_score bug is genuinely fixed; the classifier still correctly
declines to train on this narrow real news window, for a real, different
reason.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "news_price_causality", impact_df, granularity="1min", tier="tier2")
storage.write("AAPL", "news_price_causality_aggregate", agg_df, granularity="1D", tier="tier2")
# both read back with exact row-count matches

query_slice(back_impact, ["day_of_week"], {"avg_novelty": ("novelty_score", "mean")})
#  day_of_week   n  avg_novelty
#       friday  29     0.859430
#       monday  45     0.934277
#     saturday  14     0.926361
#       sunday  10     0.955113
#     thursday  54     0.880477
#      tuesday  65     0.917034
#    wednesday  51     0.922488
```

## The real number: Granger causality and correlation on the one clean real quarter

| | Value |
|---|---|
| Granger causes prices (p<0.05)? | **No** (p=0.279) |
| News-return correlation | -0.1996 (p=0.199, not significant) |
| Sample size | 43 merged hourly buckets |

Only 2023-Q1 clears the real minimum-sample floor (Granger needs ≥17
hourly buckets) — the real cached news window is narrower than a full
quarter at its edges. Recorded plainly: no significant causality or
correlation found on this real, small, single-quarter sample —
consistent with the design doc's own acknowledgment that the real
literature on this exact question is genuinely mixed, not a refutation
of the methodology.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  real `finbert_score`-null finding.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
