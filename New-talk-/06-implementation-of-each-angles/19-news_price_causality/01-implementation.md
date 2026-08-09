---
name: news_price_causality-implementation
status: phase-1-done
purpose: the real record of implementing news_price_causality's two-granularity backtest against the shared infrastructure.
---

# 19 — news_price_causality — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/compute.py` | Edited | Extracted `_compute_impact_rows()` (the former `time_format == "1min"` branch: per-article event study + novelty + significance classifier) and `_compute_aggregate_tests()` (the former tail: Granger + correlation + lag) into standalone functions. `compute()`'s external behavior unchanged — it now just calls both in sequence. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/backtest.py` | New | `run_impact_backtest()` (full standard 5-tag scheme, one row per article×ticker-mention) + `run_aggregate_tests_backtest()` (Granger/correlation/lag/significance-eval, one set per real calendar quarter). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/spec.yaml` | Edited | `time_formats` widened from `[1min, 15min, 1H, 1D]` to the decided 6 (added `5min`, `4H`) — this angle's design doc explicitly supersedes its own earlier "no-op, skip the widening" reasoning per the user's global 6-timeframe instruction. |
| `vinu-initial-analysis/tests/test_news_price_causality_backtest.py` | New | 5 tests. |

## How it was implemented

**Group B, and a genuinely different shape from every angle built so far
this session** — not a forecaster at all (real `statsmodels` Granger test,
real `scipy` Pearson correlation, one leakage-safe XGBoost classifier),
and the first angle with **two separate storage granularities** instead
of one, per the design doc's SS5:

1. **Per-article impact rows** (`run_impact_backtest`): each article's
   event-study result (price changes, abnormal return vs. SPY or
   mean-adjusted fallback, novelty score, and — when there's enough real
   data — a pre-event significance-classifier score), tagged with the
   full standard 5-tag scheme since each row has its own real timestamp.
   Already point-in-time-safe internally (no walk-forward stepping
   needed — each article's impact window only looks forward from that
   article's own timestamp, never using future articles).
2. **Per-(symbol, quarter) aggregate test results** (`run_aggregate_tests_backtest`):
   Granger causality, Pearson correlation, lag analysis, and (when
   trainable) a significance-model evaluation — one set per real calendar
   quarter, not the full tagging scheme, forced by these tests' own
   real minimum-sample floors (Granger needs ≥17 hourly buckets). The
   significance-eval step reuses **one** full-history impact-row
   computation (correct, un-clipped event windows and full trailing
   regime history) rather than recomputing per-article impact once per
   quarter, then retrains/re-evaluates the classifier fresh within each
   quarter's own chronological 70/30 split — this was a deliberate design
   choice (not in the source design doc's own worked example) to avoid
   quarter-boundary clipping the event-study windows while still
   honoring "significance-eval per quarter."

The aggregate-tests output is stored under a second angle-name bucket,
`news_price_causality_aggregate`, reusing `AngleStorage` exactly as-is —
same pattern already established by `backtesting_44_metrics`'s
`_whole_history` suffix for its own second output.

No weights store, no naive baseline — per the design doc's own
reasoning (SS7): each test's own statistic (Granger's p-value,
correlation's bootstrapped CI, the classifier's lift-over-base-rate) is
already "compared to noise" by construction.

## Testing

5 new tests, synthetic hourly-cadence fixtures (not literal 1-minute —
kept the fixture/test runtime small; the resampling logic under test
buckets by hour regardless of source cadence, so this doesn't lose
coverage of the actual logic being tested). Covers: quarter-key format,
impact rows fully tagged, empty-input produces no rows for both outputs,
aggregate rows correctly quarter-tagged, correlation values in valid
range. **Caught a real bug in my own first-draft fixture, not the
implementation**: a fixed "every Nth hour" article cadence makes
`article_count` per hourly bucket constant (always 0 or 1), which makes
`pearsonr` correctly return NaN for a zero-variance input (confirmed
real scipy behavior) — fixed by making the synthetic article count per
hour Poisson-distributed instead of a fixed cadence.

**Real-data validation (Phase 1: `1min`)**: 156 real AAPL-linked articles
(Alpaca... actually vinu-news's own cached `news.db`, spanning
2023-01-01 to 2023-01-30 — the *entire* real cached window, not a
deliberately chosen 6-month slice; this project's news cache doesn't yet
cover the full 2022-2026 date range the design assumes, a real, honest
limitation worth naming plainly) + matching real AAPL 1-minute bars
(±7 days padding around the article range, from the 2023 archive) →
268 impact rows (one per article×ticker-mention: AAPL is tagged on every
row since it's always in each article's ticker list, but many articles
also mention other tickers like TSLA/AMC/SPY, producing rows for those
symbols too with `ar_model: "none"` since only AAPL candles were fetched
for this check) in 0.35s. Of the 156 AAPL-specific rows, 52 got a real
`mean_adjusted` abnormal-return model (no `price_client` was passed for
this check, so the SPY market-model path was never exercised — a
legitimate, explicitly-labeled degradation the code already supports),
4 came back `ar_significant: true`. Storage round-trip verified for both
outputs (impact rows + the quarter-aggregate bucket), tags matched
standalone `tag_row`, `query_slice`'s grouped novelty-score-by-day-of-week
matched a hand aggregation.

**Real finding — the significance classifier never trained on this real
dataset, and that was a data-completeness fact, not a bug in this
angle**: every one of the 156 real cached articles had `finbert_score:
NULL` (confirmed directly against `news.db` — `COUNT(finbert_score) = 0`
across all 156 rows). `score_significance()`'s own leak-safety code
requires `finbert_score` as one of its non-optional numeric features
(`dropna(subset=numeric + ["ar_significant"])`), so `usable` ended up
empty and the function correctly, silently returned no scores/eval row —
exactly the documented "not enough data" behavior in
`significance_model.py`'s own docstring, not a new failure mode. Tracked
at the time as a real, cross-cutting data-completeness gap, not fixed
here (populating `finbert_score` is a `vinu-news` ingest concern, out of
scope for this angle's own backtest-wiring pass).

**Since fixed in a dedicated pass** (`known-issues.md` Resolved #4): ran
`vinu-news`'s existing (already-built, just never-run)
`backfill_finbert_sentiment` batch logic directly against the real
`news.db` — scored all 156 real articles with the real `ProsusAI/finbert`
model (downloaded once, same pattern as this project's other pretrained
models). `finbert_score` is now populated for 100% of real cached
articles (`COUNT(finbert_score) = 156`, was 0). **Re-running this angle's
real backtest afterward surfaced a second, separate, genuine limitation**:
`usable` now clears its 130-row floor (268 real impact rows, all with
complete features) — but the classifier *still* doesn't train, because
only 5 of those 268 real rows have `ar_significant: true`, split roughly
3 train / 2 test by time order, both below `MIN_TRAIN_POSITIVES=10` /
`MIN_TEST_POSITIVES=3`. This is the model's own leak-safety floor working
exactly as designed — the real cached news window (Jan 2023 only, ~156
articles) genuinely doesn't contain enough real "significant" abnormal-
return events to safely evaluate a classifier without a high risk of a
meaningless small-sample AUC. Not the same bug, not fixed here (would
need a materially wider real news cache, an ingest-volume question, not
a code fix) — recorded plainly as the honest real result rather than
treated as a lingering symptom of the finbert_score bug.

**Real finding — the aggregate tests only clear their minimum-sample
floor for one quarter of the real data**: only 2023-Q1 (43 merged hourly
buckets) has enough real data to run Granger/correlation/lag at all — the
real cached news window is narrower than a full quarter at its edges.
Granger: not causal (p=0.279). Correlation: -0.1996 (p=0.199, not
significant). Recorded plainly, consistent with the design doc's own
acknowledgment that the real literature on this question is genuinely
mixed.

**Full `vinu-initial-analysis` suite**: 311 passed (up from 306
pre-this-angle — the 5 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../known-issues.md` — the `finbert_score`-always-null data-completeness gap.
- `../../04-enhancement-of-each-angle/19-news_price_causality.md` — the decided design.
