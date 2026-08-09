---
name: backtesting_44_metrics-implementation
status: phase-1-done
purpose: the real record of implementing backtesting_44_metrics against the shared infrastructure — files touched, how it was built, how it was tested, and bugs found along the way.
---

# 02 — backtesting_44_metrics — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py` | Edited | Added missing `1min`/`5min`/`4H` entries to `PERIODS_PER_YEAR` — previously silently fell back to the `1D` value (252) via `.get(..., 252)`, which would have badly miscalculated `ann_vol`/`cagr`/`sharpe`/`sortino`/`calmar` for those three timeframes. Found before writing any backtest code, while checking whether this angle's real annualization dependency actually covered its own decided 9-timeframe target. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/compute.py` | Edited | Split into `_core_metrics()` + `_whole_history_metrics()` (pure functions, no I/O) + `compute()` (unchanged external behavior, now calls both). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/backtest.py` | New | `run_core_metrics_backtest()` (rolling, tagged) + `run_whole_history_metrics()` (once, untagged). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/backtesting_44_metrics/spec.yaml` | Edited | `time_formats` widened from `[1D, 1W, 1M, 6M]` to the decided 9 (union with the standard 6). |
| `vinu-initial-analysis/tests/test_backtesting_44_metrics_backtest.py` | New | 6 tests, see "Testing". |

## How it was implemented

This is a **Group B** angle (not a forecaster — see `Agents.md`'s group
guidance) — there's no future bar to check a prediction against, so
DLinear/ARIMA's `run_walk_forward` step/future contract doesn't apply.
Instead: `run_core_metrics_backtest` slides a fixed 100-return trailing
window through the real return series and, at each step, computes the 11
"core" metrics (`total_return`, `cagr`, `ann_vol`, `sharpe_ratio`,
`sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `avg_win`,
`avg_loss`, `win_loss_ratio`, `profit_factor`) over that window, tags the
row via `tag_row(bar_ts)`, and appends it — one row per step. Separately,
`run_whole_history_metrics` computes the 6 tail-risk/distribution-shape
metrics (`var_95`, `var_99`, `cvar_95`, `tail_ratio`, `skewness`,
`kurtosis`) once over the *entire* history and returns exactly one
untagged row — matching the decided design's explicit "stored
separately, never tagged or sliced" (§5).

Both functions reuse the exact same formulas `compute()` already had —
extracted into `_core_metrics`/`_whole_history_metrics`, not
reimplemented — so there's one source of truth for every metric formula,
not two copies that could silently drift.

**One precise semantic worth being explicit about**: `MIN_OBSERVATIONS =
100` here means 100 *return* observations (built from 101 underlying
bars), not 100 bars — the rolling window operates on the already-`pct_change()`d
series. This differs slightly from how "N=100" reads for ARIMA/DLinear
(100 candles fed in) and is worth knowing if a future reader expects the
two to mean exactly the same thing.

**Storage shape for the two outputs**: the design doc says the
whole-history metrics are "stored separately" but doesn't specify how.
Decided here: write it under a distinct `angle_name` suffix,
`backtesting_44_metrics_whole_history`, rather than inventing a new
storage mechanism — reuses `AngleStorage` exactly as-is, just as a second
angle-shaped bucket, consistent with how every other piece of this
project's storage already works.

## Testing

6 new tests, synthetic data, all pass:

- Row count formula for the rolling core-metrics loop.
- Tag correctness (matches standalone `tag_row`).
- **Direct regression check against `compute()` itself**: the rolling
  loop's step-0 window, called through `compute()` independently on the
  exact same trailing slice, produces identical `sharpe_ratio`/
  `sortino_ratio`/`max_drawdown`/`win_rate`/`cagr` — proof the extraction
  didn't silently change any formula. This test initially failed with an
  off-by-one window-size mismatch — traced to the test itself (comparing
  against a 100-bar slice when the rolling loop's window is actually 100
  *returns*, built from 101 bars), not the implementation; fixed in the
  test, not the code.
- Whole-history metrics: exactly one untagged row, matches `compute()`'s
  own full-series values.
- Too-short history produces zero core rows (no crash).

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars
(Alpaca) → 25 core rows + 1 whole-history row. Tags matched standalone
`tag_row`. Storage round-trip: both outputs written through the real
`AngleStorage` under their respective angle names, read back with exact
row-count matches. `query_slice` grouping by `day_of_week` matched a
hand-computed pandas `groupby` exactly. Full numbers in
`02-real-scenario.md`.

**Phase 2 (deferred)**: `5min`, `15min`, `1H`, `4H` (the other finer
timeframes the rolling backtest applies to), plus `1min`. `1W`/`1M`/`6M`
are intentionally **not** run through the rolling backtest at all — a
100-period rolling window needs 100 weeks/months/half-years of history,
which this project's 2022-2026 date range doesn't have; those three stay
on the existing single-shot `compute()` path only, consistent with the
design doc's own low-sample-size flag on them.

**Full `vinu-initial-analysis` suite**: 233 passed (up from 227 pre-this-angle
— the 6 new tests), 2 skipped, the same 11 pre-existing `shock_clustering`/
`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `00-plan.md` — the pre-implementation plan this followed.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/02-backtesting_44_metrics.md` — the
  decided design.
