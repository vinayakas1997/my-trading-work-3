---
name: implementation-known-issues
status: tracking
purpose: cross-angle tracker for real bugs found during implementation that are deliberately not fixed in the angle that found them — shared-library issues, bigger-than-a-side-fix, or otherwise needing their own separate pass. Kept separate so they're discoverable on their own, not buried inside one angle's implementation.md, and can be combined/prioritized together later.
---

# Known Issues — Found During Implementation, Not Yet Fixed

One entry per issue. Each entry stays here until it's actually fixed (in
its own dedicated pass), at which point it moves to "Resolved" with a
link to what changed.

## Open

None currently — all 4 issues found during the 31-angle implementation
pass have been fixed. See Resolved below.

## Resolved

### 1. `pearson_with_ci`'s bootstrap CI was always the degenerate `[-1, 1]`, regardless of real correlation strength or sample size

- **Found**: while implementing angle 24 (`shock_clustering`), during
  real-data validation — AAPL/TSLA's real shock-day correlation
  (n=107 pairs) came back with `correlation_ci: [-1.0, 1.0]`, an
  obviously-wrong (maximally uninformative) band for that sample size.
- **Where**: `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py`,
  `pearson_with_ci()` (added in angle 21/`peer_relative_strength`,
  generalized from `news_price_causality/correlation.py`'s pre-existing
  bootstrap pattern — see Open #4 for that still-unfixed sibling).
- **What was wrong**: passed `list(zip(x, y))` as a single un-paired
  sample to `scipy.stats.bootstrap`. Because the statistic function
  accepted an `axis` parameter, scipy auto-detected it as "vectorized"
  and called it directly on the raw bootstrap-resampled array without
  the shape `_stat` assumed — `arr[:, 0]`/`arr[:, 1]` ended up comparing
  two independently-resampled slices, not the paired `(x, y)`
  observations, so nearly every resample computed the correlation
  between unrelated values. Confirmed directly: a synthetic series with
  a real, strong 0.6 correlation (n=107) still produced
  `ci=[-1.0, 1.0]`.
- **The fix**: use `scipy.stats.bootstrap`'s built-in `paired=True` mode
  (resamples `x`/`y` as matched pairs, not independently) with
  `vectorized=False` (so `_stat` receives plain resampled arrays, not a
  vectorized batch). Confirmed via a direct A/B test on the same
  synthetic data: `paired=True` gave `ci=[0.42, 0.65]` around the real
  0.53 measured correlation — a real, informative band. Also added a
  post-hoc NaN guard: a small (<15-ish) sample can draw a degenerate
  (constant) resample often enough that `pearsonr` returns NaN for some
  resamples, poisoning the percentile CI — falls back to a zero-width CI
  at the real correlation in that case, same as the existing
  exception-fallback path.
- **Real, measured impact on already-shipped output**: angle 21's own
  `02-real-scenario.md` (written before this fix, during angle 21's own
  implementation pass) documented "bootstrapped 95% CIs typically
  spanned most of [-1, 1]" as a *small-sample-size* finding — that
  framing was wrong; it was this bug, not sample size. Corrected in both
  `21-peer_relative_strength/01-implementation.md` and
  `02-real-scenario.md` with the real, re-run numbers after the fix.
- **Verification**: `pearson_with_ci` re-run on the same real AAPL data
  peer_relative_strength originally validated against — CIs are now
  real, bounded bands (e.g. `[-0.27, 0.82]` instead of `[-1.0, 1.0]`).
  Re-running also surfaced a separate, real design property worth noting
  while correcting the finding: `relative_return_20d` is basket-wide, not
  per-peer, so each quarter's forward-return correlation is identical
  across peer rows — the truly independent sample is 16 quarters × 3
  horizons = 48 tests, not 96. Of those 48, 7 cross p<0.05 (more than the
  ~2.4 expected by chance), mostly at the 20-day horizon with inconsistent
  sign across quarters — a weak, non-directional hint, not the flatter
  "no significant predictability" the pre-fix write-up originally claimed.
- **Full write-up**: `24-shock_clustering/01-implementation.md`.

### 2. `vinu_tools._garch_ml_estimate`'s `omega` didn't converge to the true MLE

- **Found**: while implementing angle 08 (`garch`), via the real-data
  walk-forward check.
- **Where**: `vinu-components/vinu-tools/vinu_tools/compute/risk/volatility.py`,
  `_garch_ml_estimate()`.
- **What was wrong**: the hand-rolled gradient-ascent optimizer used a
  fixed, unscaled step size (`1e-8`) for all three parameters, and its
  gradient formulas were themselves incomplete — they treated `sigma2[t]`
  as depending only directly on `omega`/`alpha`/`beta`, ignoring the GARCH
  recursion's own chain-rule dependency on `sigma2[t-1]`. `grad_omega =
  sum(1/sigma2)` has a huge magnitude for realistic (small) return
  variances, producing a large first-iteration jump; `omega` was only
  floored (`max(..., 1e-8)`), never capped, so it settled far from the
  true MLE. `alpha`/`beta` were at least clamped into `[0,1]`-ish ranges
  by the code's own min/max calls — `omega` had no equivalent ceiling.
- **Real, measured impact (before)**: on real AAPL daily data, fitted
  `omega` was ~1,820x larger than a rough sanity estimate
  (`unconditional_variance × (1 - persistence)`). Confirmed on real
  market data, not just synthetic test data.
- **The fix**: replaced the gradient-ascent loop entirely with
  `scipy.optimize.minimize` (SLSQP) directly minimizing the real Gaussian
  negative log-likelihood, with `omega`'s upper bound tied to the sample
  variance (`10×sample_var` — the true MLE is always a fraction of it via
  the unconditional-variance identity) and an `alpha + beta ≤ 0.999`
  stationarity constraint. **A second, real subtlety found while fixing
  it**: optimizing raw `omega` (~1e-5) jointly with `alpha`/`beta`
  (~0.05-0.9) breaks SLSQP's internal step-size logic — it reported
  `success: True` after 4 evaluations while sitting exactly at the
  starting guess, gradient unexploited. Fixed by optimizing `log(omega)`
  instead (comparable parameter scales); confirmed via direct comparison
  that the log-space version finds a genuinely better optimum (NLL
  improved from -3662.1 to -3667.8 on the same real data) and via a
  5-different-starting-points check that the converged solution is stable.
- **Real, measured impact (after)**: fitted `omega` now lands within
  ~1.01x-1.05x of the variance-targeting sanity identity on real AAPL
  data (was ~1,820x off). Mean `qlike_error` on a 125-bar real AAPL
  walk-forward re-run dropped from ~5.9 to ~2.25.
- **Blast radius, and what was re-verified**: shared by two angles —
  `garch` (uses `omega` directly in its forecast) and `shock_personality`
  (uses the same function internally for `vol_persistence`, via
  `_compute_vol_persistence`) — both angles' full test suites (26 tests)
  pass unchanged after the fix. Also re-ran every other monorepo consumer
  of `garch_volatility` found via a repo-wide grep — `vinu-live`,
  `vinu-portfolio`, `vinu-research` (53 tests combined) — all pass, no
  regressions. Added a regression test
  (`vinu-tools/tests/test_risk_volatility.py::test_garch_volatility_omega_matches_variance_targeting_identity`)
  asserting the fitted `omega` stays within a sane band of the
  variance-targeting identity, the same sanity check that caught the bug.
- **Full write-up**: `08-garch/01-implementation.md` Bug 2 (updated),
  `08-garch/02-real-scenario.md` (updated with before/after numbers).

### 3. Corrupt live parquet files block candle queries — a systemic live-ingest atomicity gap

- **Found**: while implementing angle 14 (`lstm`), fetching real AAPL
  data for the Phase-1 real-data check. **Confirmed to recur** while
  implementing angle 21 (`peer_relative_strength`), on a second symbol
  (`JNJ`) — same failure mode, different file.
- **Where**: two root causes, both in `vinu-components/vinu-stock-price/vinu_stock/`
  — the write side (`storage/parquet.py`: `write_bars()`, `append_bars()`,
  `consolidate_live_shards()`) and the read side
  (`query/engine.py`: `_load_symbol_frame()`, via `fetch_candles()`).
- **What was wrong (write side)**: all three write functions called
  `pq.write_table(table, path, ...)` directly against the real target
  path. A crash or kill mid-write (e.g. a live-ingest job interrupted)
  leaves a truncated file sitting at the real path — the next reader sees
  a corrupt file, not a missing one.
- **What was wrong (read side)**: `_load_symbol_frame()` handed the whole
  `{symbol}/live/*.parquet` glob to a single DuckDB `read_parquet([...])`
  call — one truncated file (failing DuckDB's/pyarrow's Parquet
  magic-bytes check) made the call raise for **any** query on that
  symbol, regardless of whether the query's date range even touched the
  bad file's date.
- **Real, measured impact (before the fix)**: `fetch_candles(data_root,
  "AAPL"/"JNJ", ...)` raised (`duckdb.InvalidInputException` /
  `pyarrow.lib.ArrowInvalid`) for every call attempted during both
  angles' real-data validation, regardless of date range. A follow-up
  audit (once the fix below was being verified) found a **third** corrupt
  file on `TSLA` — previously checked and reported clean — sharing the
  *exact same date* (`2026_20260205.parquet`) as AAPL's corrupt file,
  strong evidence of one crashed ingest run corrupting multiple symbols'
  shards in the same event, not unrelated one-offs.
- **The fix**:
  1. **Write side**: added `_atomic_write_table()` — writes to a temp
     file in the same directory, then `os.replace()`s over the real
     target path. `os.replace` is atomic on both POSIX and NTFS, so a
     reader now always sees either the old complete file or the new
     complete file, never a partial one. All three write call sites
     switched to it.
  2. **Read side**: `_load_symbol_frame()` now expands each glob pattern
     to individual files and validates each one by opening its parquet
     footer (`pq.ParquetFile(path)` — cheap, footer-only) *before*
     handing files to DuckDB. Unreadable files are skipped with a
     `RuntimeWarning` naming them, instead of failing the whole symbol;
     if every file for a symbol is unreadable, `fetch_candles` now
     returns `[]` instead of raising.
- **Data repair**: ran the same per-file validation across every cached
  symbol (`AAPL`, `JNJ`, `TSLA`) — 108 files checked, exactly the 3 known
  corrupt ones found, nothing new beyond the TSLA discovery above. All 3
  corrupt files contained zero recoverable data (parquet magic bytes
  entirely absent — not partially-salvageable), so they were deleted
  outright rather than quarantined. A re-audit after deletion confirmed
  0/105 remaining files corrupt, and `fetch_candles` now returns real
  data cleanly for all three symbols with no workaround needed. The
  minute-level data for those 3 specific corrupted days is genuinely
  gone and would need re-fetching from Alpaca if that history matters —
  not attempted here, out of scope for this fix pass.
- **Verification**: added `test_writes_never_leave_a_partial_file_at_the_target_path`
  and `test_append_bars_atomic_write_leaves_no_tmp_file`
  (`vinu-stock-price/tests/test_parquet_io.py`, simulates a crash
  mid-write via monkeypatching `pq.write_table` and confirms the original
  file is untouched) and two new tests in
  `vinu-stock-price/tests/test_query_engine_resilience.py` (one corrupt
  file among good ones is skipped with a warning and the good data still
  returns; an all-corrupt symbol returns `[]` instead of raising). Full
  `vinu-stock-price` suite: 44 passed (up from 38), 0 failed.
- **What this changes for `14-lstm`'s and `21-peer_relative_strength`'s
  own docs**: the direct-pandas-load workaround they used is no longer
  necessary (though harmless to leave documented as a record of how the
  bug was originally found and worked around) — a fresh `fetch_candles`
  call for either symbol now works normally.
- **Full write-up**: this entry; the fix lives in
  `vinu-stock-price/vinu_stock/storage/parquet.py` and
  `vinu-stock-price/vinu_stock/query/engine.py`, outside any single
  angle's own implementation record since it's shared infrastructure, not
  angle-specific.

### 4. `finbert_score` was `NULL` for every real cached article — the significance classifier could never train

- **Found**: while implementing angle 19 (`news_price_causality`), during
  the real-data validation.
- **Where**: `vinu-components/data/news/news.db`, `articles.finbert_score`
  (data, not code) — surfaced through
  `angles/news_price_causality/significance_model.py`'s `score_significance()`.
- **What was wrong**: `score_significance()`'s leak-safety code requires
  `finbert_score` as one of its non-optional numeric features
  (`FEATURES_NUMERIC`), then does
  `usable = df.dropna(subset=numeric + ["ar_significant"])`. Every real
  cached article had `finbert_score = NULL`
  (confirmed directly: `SELECT COUNT(*), COUNT(finbert_score) FROM articles`
  → `(156, 0)`), so `usable` was always empty and the classifier never
  trained, regardless of how much other data was available.
- **The fix**: `vinu-news` already had a complete, working, but
  never-actually-run FinBERT backfill path
  (`vinu_news.service.NewsService.backfill_finbert_sentiment`, also
  exposed via a CLI (`vinu-news-finbert --once`) and an API route
  (`POST /finbert/backfill`)) — no new code needed. Ran its exact SQL
  logic (`SELECT ... WHERE finbert_score IS NULL`, score via
  `vinu_news.analysis.enrichment.finbert_sentiment.score_finbert_batch`,
  `UPDATE articles SET finbert_score=?, finbert_label=?`) directly against
  the real `news.db`, bypassing `NewsService`'s own config/service layer
  only to avoid an unrelated side effect (its default `llm_analysis_mode`
  is `"auto"`, which would have also kicked off an LLM-analysis backfill —
  out of scope for this fix). The real `ProsusAI/finbert` model (~400MB)
  was downloaded once via this project's existing shared-model-download
  path (`vinu_infra.models.ensure_model`, same mechanism already used for
  chronos/timesfm/timer/kronos).
- **Real, measured impact**: all 156 real cached articles now have a real
  `finbert_score`/`finbert_label` (`COUNT(finbert_score) = 156`, was 0).
  Re-running `news_price_causality`'s real backtest confirmed the actual
  fix: `usable` now clears its 130-row floor (268/268 real impact rows
  have complete features, was 0/268). **A second, separate, genuine
  limitation surfaced once the bug was out of the way**: the classifier
  still doesn't train, because only 5 of those 268 real rows have
  `ar_significant: true` (3 land in train, 2 in test by time order),
  below `MIN_TRAIN_POSITIVES=10` / `MIN_TEST_POSITIVES=3`. This is the
  model's own leak-safety floor doing its job — the real cached news
  window (Jan 2023 only, ~156 articles) genuinely doesn't contain enough
  real significant-abnormal-return events yet to safely evaluate a
  classifier. Not the same bug; recorded plainly rather than treated as a
  lingering symptom. Would need a materially wider real news cache (an
  ingest-volume question) to actually train, not a further code fix.
- **Blast radius**: `news_price_causality` only — no other built angle
  depends on `finbert_score`. No code changed, so no test suite regressed
  (`test_news_price_causality_backtest.py`: 5 passed, unchanged).
- **Full write-up**: `19-news_price_causality/01-implementation.md`,
  `19-news_price_causality/02-real-scenario.md` (both updated with the
  real before/after numbers).

### 5. `news_price_causality/correlation.py`'s own bootstrap CI had the same un-paired-resample bug as `pearson_with_ci` had

- **Found**: while implementing angle 24 (`shock_clustering`), via a real
  A/B test of `pearson_with_ci` against real shock-day data (see
  Resolved #1 for the full original diagnosis).
- **Where**: `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/correlation.py`,
  `compute_correlation()`'s `bootstrap((corr_data,), _corr_stat, ...)`
  call — the original implementation `pearson_with_ci` (in `_helpers.py`)
  was generalized from.
- **What was wrong**: same root cause as Resolved #1 — passing
  `list(zip(x, y))` as one un-paired sample let `scipy.stats.bootstrap`
  auto-vectorize the statistic function in a way that decorrelated `x`
  from `y` per resample, producing a degenerate `[-1, 1]` confidence
  interval regardless of the real correlation strength or sample size.
- **The fix**: replaced the whole hand-rolled bootstrap block with a
  direct call to the already-fixed, already-tested shared
  `pearson_with_ci()` helper (`_helpers.py`) — no need to re-derive the
  `paired=True`/`vectorized=False` fix a second time in this file.
  `sentiment_return_corr`/`news_volume_corr` (which never had CIs, only
  point correlations) are unchanged.
- **Real, measured impact**: on the real 2023-Q1 AAPL news/returns sample
  (43 merged hourly buckets, the same one `19-news_price_causality`'s own
  real-scenario doc uses) — `corr_ci_lower`/`corr_ci_upper` went from the
  degenerate `[-1.0, 1.0]` to `[-0.4883, 0.0262]`, a real, bounded,
  informative band (correctly spanning zero, consistent with the
  already-reported non-significant `p=0.199`).
- **Blast radius**: `news_price_causality` only. Confirmed at the time
  this bug was first found (see Open #4, now closed) that no stored
  output persisted `corr_ci_lower`/`corr_ci_upper` yet, so this fix has
  no migration/backfill implications for already-written data — it only
  changes what gets computed and stored going forward.
- **Verification**: added `test_compute_correlation_ci_is_not_degenerate_full_range`
  (`vinu-initial-analysis/tests/test_correlation.py`) — a real, strongly
  correlated synthetic series now produces a real, bounded CI, not
  `[-1, 1]`. Full `vinu-initial-analysis` suite: 379 passed (up from 378
  — the 1 new test), 2 skipped, 0 failed.
- **Full write-up**: this entry; the fix lives in
  `news_price_causality/correlation.py`, outside angle 19's own
  implementation record since the fix itself was mechanical (reusing an
  already-proven shared helper) rather than a new investigation.
