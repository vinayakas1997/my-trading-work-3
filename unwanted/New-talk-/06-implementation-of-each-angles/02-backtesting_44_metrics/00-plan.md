---
name: backtesting_44_metrics-implementation-plan
status: proposed
purpose: what will actually be done to implement backtesting_44_metrics against the shared infrastructure, and how it will be checked, written before any code is touched.
---

# 02 — backtesting_44_metrics — Implementation Plan

## What the real code looks like today (`angles/backtesting_44_metrics/compute.py`)

Already read directly: `compute()` is a single-shot function — given the
full `bars` history, it computes all 18 metrics (11 "core" + `ann_vol` +
6 whole-history-only) once over the whole series and returns one row. No
rolling/time-sliced computation exists yet, no walk-forward loop, nothing
tagged.

## Why this is Group B, not Group A

This angle isn't a forecaster — there's no "prediction" to check against
a future bar, so DLinear/ARIMA's `run_walk_forward` (step_fn +
future-bar-comparison contract) doesn't fit. What the decided design
(`04-enhancement-of-each-angle/02-backtesting_44_metrics.md` §3-§5) wants
instead: at each point in time, compute the 11 "core" metrics over a
*trailing* window of returns ending there, tag that snapshot with
session/day/week/etc., and store one row per step — a rolling
point-in-time computation, not a forecast-and-check loop. Per
`Agents.md`'s Group B guidance, this gets its own small rolling-window
loop, not a forced-fit `step_fn`.

## What I will actually do

1. **Write `angles/backtesting_44_metrics/backtest.py`** with two
   functions, matching the design doc's explicit "stored separately" split:
   - `run_core_metrics_backtest(symbol, timeframe, bars) -> pd.DataFrame`
     — slides a fixed-size trailing window through `bars`, and at each
     step computes the 11 core metrics (`total_return`, `cagr`, `ann_vol`,
     `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`,
     `win_rate`, `avg_win`, `avg_loss`, `win_loss_ratio`, `profit_factor`)
     over that window, tags the row via `tag_row(bar_ts)`, and appends it.
     One row per step, matching Layer 1 in the design doc.
   - `run_whole_history_metrics(symbol, timeframe, bars) -> pd.DataFrame`
     — the 6 tail-risk/distribution metrics (`var_95`, `var_99`,
     `cvar_95`, `tail_ratio`, `skewness`, `kurtosis`), computed once over
     the *entire* history, never tagged, one row — matching the design
     doc's explicit "stored separately, never tagged or sliced."
   - Both reuse the exact same metric formulas already in `compute.py`
     (extracted into two small pure helpers, `_core_metrics`/
     `_whole_history_metrics`, so nothing is duplicated between the
     existing single-shot `compute()` and the new rolling backtest).
   - No weights store — nothing is trained here.

2. **Rolling window size: 100, extending the project's established
   convention.** The design doc doesn't pin an explicit number for the
   core-metrics rolling window (unlike ARIMA's explicit N=100). Rather
   than leave this undecided, I'm extending the same N=100 convention
   already applied to ARIMA/DLinear for consistency — flagged here as my
   own fill of a real gap in the decided doc, not something the doc
   itself specifies.

3. **Fixed a real bug in `_helpers.py` before this angle can even use it
   correctly** (already done, ahead of this plan being written): the
   `PERIODS_PER_YEAR` table `ann_factor()`/`periods_per_year()` read from
   was missing `1min`/`5min`/`4H` entries entirely — any of those three
   would have silently fallen back to the `1D` value (252) via
   `.get(..., 252)`, badly miscalculating `ann_vol`/`cagr`/`sharpe`/
   `sortino`/`calmar` for those timeframes. Added the missing three
   (`98280`/`19656`/`410`, derived the same way the existing entries were
   — trading-hours-per-day × 252).

4. **Widen `spec.yaml`** from its current 4 timeframes (`1D, 1W, 1M, 6M`)
   to the decided 9 (union with the standard 6: `1min, 5min, 15min, 1H,
   4H, 1D, 1W, 1M, 6M`) — per the design doc's explicit decision. The
   rolling core-metrics backtest only makes sense for the finer 6
   (rolling a 100-period window over `1W`/`1M`/`6M` bars needs 100 weeks/
   months/half-years of history, which this project's 2022-2026 date
   range doesn't have) — `1W`/`1M`/`6M` stay as the existing single-shot
   `compute()` call only, consistent with the design doc's own
   low-sample-size flag on those three.

5. **Unit tests** — `tests/test_backtesting_44_metrics_backtest.py`,
   covering: row count for the rolling core-metrics loop, tag
   correctness, that the whole-history metrics come back as exactly one
   untagged row, and that the core-metric formulas match the existing
   `compute()`'s own formulas on the same data (a direct regression check
   against the code this was extracted from).

## How I will check it

Same real-data policy as ARIMA (`Agents.md`): Alpaca, 1-minute bars
aggregated to every other timeframe, ~6 months, AAPL. Phase 1 (per the
two-phase policy): `1D`, the coarsest of the 6 finer timeframes this
angle's rolling backtest actually applies to. Checklist:

1. Bar sanity, row-count formula, tag spot-check — same as every other
   angle.
2. **Metric correctness check specific to this angle**: compute the core
   metrics via the new rolling loop for the last window in the series,
   and independently compute the same window's metrics by calling the
   *existing* `compute()` directly on just that slice — confirm they
   match exactly. This is the direct proof the extraction in step 1
   didn't silently change any formula.
3. Whole-history metrics: confirm exactly one row comes back, matches
   `compute()`'s own `var_95`/`var_99`/`cvar_95`/`tail_ratio`/`skewness`/
   `kurtosis` fields when run on the full real dataset.
4. Storage + query round-trip (write both the core-metrics rows and the
   whole-history row, read both back, run a real `query_slice` grouping
   on the core rows).
5. Full test suite, both packages, confirm no new failures.
6. Write `01-implementation.md`/`02-real-scenario.md`, update `../plan.md`.

## Open items

None needing a call before starting — the rolling-window-size gap (item
2 above) is being filled with the already-established N=100 convention
rather than raised as a new question, consistent with how ARIMA's
missing `N_15MIN` refit cadence was handled.
