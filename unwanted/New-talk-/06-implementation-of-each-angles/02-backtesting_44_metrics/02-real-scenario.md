---
name: backtesting_44_metrics-real-scenario
status: phase-1-done
purpose: one concrete, real example proving backtesting_44_metrics' rolling core-metrics loop and whole-history metrics actually work — real Alpaca data in, real output back, real storage/query round-trip.
---

# 02 — backtesting_44_metrics — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for ARIMA's `1D`
Phase 1 check.

## The calls

```python
from vinu_initial_analysis.angles.backtesting_44_metrics.backtest import (
    run_core_metrics_backtest, run_whole_history_metrics,
)

core = run_core_metrics_backtest("AAPL", "1D", bars)   # 25 rows
whole = run_whole_history_metrics("AAPL", "1D", bars)  # 1 row
```

## Real output — core metrics (first row)

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1783296000, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "monday", "week_of_month": 1, "month": 7, "quarter": 3,
  "n_observations": 100,
  "total_return": 0.139271, "cagr": 0.388995, "ann_vol": 0.275048,
  "sharpe_ratio": 1.4143, "sortino_ratio": 1.9312,
  "max_drawdown": -0.126858, "calmar_ratio": 3.0664,
  "win_rate": 0.55, "avg_win": 0.012995, "avg_loss": -0.012649,
  "win_loss_ratio": 1.0274, "profit_factor": 1.2557
}
```

## Real output — whole-history metrics (the one, untagged row)

```json
{
  "symbol": "AAPL", "timeframe": "1D",
  "n_observations": 124,
  "var_95": -0.022842, "var_99": -0.057409, "cvar_95": -0.041787,
  "tail_ratio": 1.261, "skewness": -0.4948, "kurtosis": 1.9254
}
```

No `session`/`bar_ts`/tag columns at all — confirmed by checking the
actual DataFrame's columns, not just describing intent.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "backtesting_44_metrics", core, granularity="1D", tier="tier2")
# -> run_id "7f4800e377dd", read back: 25 rows, exact match

storage.write("AAPL", "backtesting_44_metrics_whole_history", whole, granularity="1D", tier="tier2")
# -> run_id "0eadfe7c9905", read back: 1 row, exact match

query_slice(core, ["day_of_week"], {"avg_sharpe": ("sharpe_ratio", "mean")})
#   day_of_week   n  avg_sharpe
#        friday   5     2.60060
#        monday   5     2.16590
#      thursday   5     2.60508
#       tuesday   5     2.22086
#     wednesday   5     2.48154
```

Independently checked against a hand-written pandas
`groupby("day_of_week")["sharpe_ratio"].agg(["mean","count"])` on the same
raw rows and matched exactly.

## Proving the extraction is correct, not just "output exists"

The strongest check here wasn't tagging or storage — it was confirming
`_core_metrics`/`_whole_history_metrics` (pulled out of the old
single-shot `compute()`) still compute *exactly* what `compute()` always
computed. Called `compute()` directly on the same 101-bar window the
rolling loop's first step used internally, and compared field by field:

```python
window_bars = bars.iloc[0:101]
direct = compute("AAPL", bars=window_bars, time_format="1D").iloc[0]
# direct["sharpe_ratio"] == core.iloc[0]["sharpe_ratio"]  -> True
# direct["sortino_ratio"] == core.iloc[0]["sortino_ratio"] -> True
# (and max_drawdown, win_rate, cagr — all exact matches)
```

This is what actually caught a real bug — not in the implementation, in
the *first version of this very check*: comparing against a 100-bar slice
instead of 101 gave a mismatched `sortino_ratio` (`-1.4909` vs `-1.3878`),
which traced back to the rolling window being 100 *returns* (101 bars),
not 100 bars. Fixed the check once that was understood; the underlying
metric code was correct the whole time.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  off-by-one finding above in full.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` —
  the checklist this scenario satisfies (Phase 1: `1D`).
