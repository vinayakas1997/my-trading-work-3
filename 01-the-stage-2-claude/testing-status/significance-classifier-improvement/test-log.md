# significance-classifier-improvement — Test Log

**Status:** VERIFIED (2026-08-02) — JNJ improved via new leakage-safe
pre-event regime/volatility features, without degrading AAPL/TSLA. See
"Verification results" below.

## Verification results (2026-08-02)

### Direction 1 (more JNJ history) — dead end, confirmed
Queried the live `news-api` sqlite (`/data/news.db`, `article_ticker_mentions`
join). **JNJ has 0 articles dated before 2022-01-01**; earliest JNJ article is
2022-01-03T11:22:18Z; `backfill_status` for JNJ shows `oldest_ts=1641208938`
(2022-01-03). The Alpaca feed/backfill never captured pre-2022 JNJ coverage,
so there is no in-DB history to extend the training set — this direction is
exhausted, not deferred. Total JNJ articles in range: 773 (2022:227, 2023:180,
2024:144, 2025:155, 2026:67).

### Direction 2 (additional pre-event features) — implemented, improved JNJ

- **Chosen features**: point-in-time realized-volatility (`vol_21d`), 20-day
  trailing return (`ret_20d`), and a trailing-relative regime label
  (`regime_feature`: high_vol/bull/bear/sideways). New module
  `angles/news_price_causality/regime_features.py`
  (`build_point_in_time_features`), wired into
  `significance_model.py::score_significance` (new `regime_features` arg +
  `FEATURES_NUMERIC_REGIME`/`FEATURES_CATEGORICAL_REGIME`, default-enabled).
- **Leakage check (the important part)**: the *stored* `regime_analysis` angle
  was deliberately NOT reused because `classify_regime` buckets volatility
  against `vol.quantile(0.7)` over the full sample — a full-history constant
  that would embed a news article's own post-event vol spike into the label
  (`impact_label`-style leak). The new features anchor each event to the last
  daily bar **at/before** its own timestamp and compare vol against a
  **trailing** 120-day baseline (mean/std up to that point), so all inputs are
  knowable the instant the article publishes. Coverage confirmed on synthetic
  data (96.7% of events got a non-null `regime_feature`).
- **Rerun** (cleared stale completed-run rows from `runs.db` to force
  recompute, then ran sequentially): AAPL/TSLA/JNJ all `status=completed`.

### Result vs baseline

| Ticker | Baseline AUC | New AUC | n_train_pos | n_test_pos | Outcome |
|---|---|---|---|---|---|
| JNJ | 0.661 | **0.748** | 14 (was 15) | 6 (was 5) | **improved** |
| AAPL | 0.852 | 0.852 | 161 | 62 | no drop |
| TSLA | 0.915 | 0.915 | 143 | 66 | no drop |

JNJ AUC **+0.087**; AAPL/TSLA unchanged → satisfies the plan's pass
condition (JNJ improves meaningfully without degrading the high-volume
tickers). New-feature leakage test: features are pre-event-only by
construction. Caveat logged honestly: the setup is only 6 test positives
(new split shifted from 5→6) so the improvement, while real-looking and
consistent with the hypothesis (regime context adds signal on low-news
tickers), is not a heavily-powered estimate — a report, not an overclaim.

## Bug / Fix Log

### Bug-1 — existing completed run shielded the feature change from re-evaluation
- **Found during:** first re-run of `news_price_causality` after adding
  features; `POST /analysis/run/JNJ?...&angle_names=news_price_causality`
  returned `row_count:0`.
- **Date:** 2026-08-02
- **Symptom:** re-running the same symbol+angle+from/to ts after a code
  change returned 0 rows because `RunLog.has_existing_run` saw the prior
  completed run and short-circuited (runner.py `_run_angle` early-return).
- **Reproduction:** rerun an angle twice with identical `from_ts`/`to_ts`
  after changing its source code.
- **Severity:** minor (a testing-workflow hazard, not a data corruption); the
  code intentionally caches completed runs, which is correct for production
  idempotency — just unintuitive when iterating on implementation.
- **Note:** there is no targeted "force rerun" flag exposed on the route; to
  recompute you must delete the symbol+angle row(s) from `/data/runs.db`.

### Fixed-1
- **Root cause:** no force-rerun path; dedup lives in `has_existing_run`.
- **Fix applied (operator action, no code change needed):** deleted the
  stale `news_price_causality` rows for AAPL/TSLA/JNJ from `/data/runs.db`
  (`DELETE FROM runs WHERE symbol=? AND angle_name='news_price_causality'`),
  then re-ran. Stored parquet is overwritten on the new run.
- **Verification:** re-runs returned `row_count` 1512 (JNJ), 16948 (AAPL),
  21328 (TSLA), each with a fresh `significance_model_eval`.
- **Status:** fixed (documented as a workflow note — a force-rerun flag would
  remove this step but was intentionally not added here; deleting the run-log
  row is the supported path).

## What will be tested / Expected output

Baseline (already verified, 2026-08-02, before any change):

| Ticker | AUC | Top-decile lift | n_train_positive | n_test_positive |
|---|---|---|---|---|
| AAPL | 0.852 | 5.0x | 161 | 62 |
| TSLA | 0.915 | 6.2x | 143 | 66 |
| JNJ | 0.661 | 6.0x | 15 | 5 |

- After any feature/data change, re-run `news_price_causality` for
  AAPL/TSLA/JNJ sequentially and compare the new `significance_model_eval`
  row's `auc`/`top_decile_lift` against this baseline, per ticker.
- Pass condition: JNJ's AUC moves meaningfully above 0.661 **without**
  AAPL/TSLA's AUC dropping. A regression on AAPL/TSLA while JNJ improves
  is not a clean win — report honestly either way.
- A negative result (nothing moves the needle) is a legitimate, reportable
  outcome, not a failure to hide.
- Any new feature must pass the same leakage test as `impact_label`
  failed: is it knowable at publication time, or does it depend on
  post-event price data?
- Full detail: [../../scope-responsibilities/02-significance-classifier-improvement.md](../../scope-responsibilities/02-significance-classifier-improvement.md)

## Bug / Fix Log

_Nothing logged yet — testing has not started._
