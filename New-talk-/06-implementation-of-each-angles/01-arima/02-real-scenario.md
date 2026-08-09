---
name: arima-real-scenario
status: done
purpose: one concrete, real example proving ARIMA's walk-forward backtest actually works — real Alpaca data in, the real function call, real output back, real storage/query round-trip, and the real naive-baseline comparison.
---

# 01 — ARIMA — Real Scenario

Real AAPL bars, fetched from **Alpaca** (`GET .../stocks/AAPL/bars?timeframe=1Min&...&feed=iex`),
~6 months of 1-minute data (49,757 real bars), then aggregated to every
other declared timeframe with the real `vinu_stock.query.aggregate.aggregate_bars`.

## The call (1D shown; identical shape for every timeframe)

```python
from vinu_initial_analysis.angles.arima.backtest import run_arima_backtest

df = run_arima_backtest("AAPL", "1D", bars, data_root)
```

125 real daily bars in, `min_observations=100` consumed before the first
step, `25` output rows back — matches `125 - 100` exactly.

## The output: real results

First row:

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 100,
  "order": {"p": 2, "d": 1, "q": 2}, "aic": 596.61,
  "forecast": 305.43,
  "confidence_interval": [296.36, 314.50],
  "confidence_level": 0.95,
  "actual_price": 312.73,
  "hit": 1,
  "abs_error": 7.30, "squared_error": 53.29
}
```

`hit: 1` here because `312.73` (the real next close) falls inside
`[296.36, 314.50]` — the CI-coverage hit definition, not a direction
match. Last row (step 24, the most recent):

```json
{
  "bar_ts": 1785974400, "step_index": 24,
  "order": {"p": 2, "d": 1, "q": 2}, "aic": 615.21,
  "forecast": 313.13,
  "confidence_interval": [303.17, 323.09],
  "actual_price": 313.29,
  "hit": 1,
  "abs_error": 0.16, "squared_error": 0.03
}
```

A much tighter miss here (`abs_error` 0.16 vs. 7.30) — real variation
across real steps, not a constant result.

## Real numbers across all 6 timeframes

| Timeframe | Real bars | Rows | Runtime | CI-coverage |
|---|---|---|---|---|
| 1D | 125 | 25 | 14.7s | 80.0% |
| 4H | 321 | 221 | 106.7s | 90.5% |
| 1H | 1011 | 911 | 421.2s | 93.0% |
| 15min | 3659 | 3559 | 459.2s | 93.6% |
| 5min | 10431 | 10331 | 469.5s | 93.2% |
| 1min | 49757 | 49657 | 658.5s | 88.8% |

## Refit cadence actually working, not just configured

`1H` refits its ARIMA model on every single step (911 real grid-search
fits). `1min` refits only every 60th step (~828 real fits out of 49,657
steps) — the other steps extend the previous fit with
`.append(refit=False)` instead. Confirmed for real, not assumed: a
`monkeypatch`-based test (`tests/test_arima_backtest.py::test_1min_timeframe_reuses_prior_state_between_refits`)
counts actual calls into the real grid-search function and asserts the
count matches the expected refit count, strictly less than the total step
count.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "arima", df, granularity="1D", tier="tier2")
# -> run_id "c4eeab7e4b34"
storage.read_latest("AAPL", "arima", granularity="1D", tier="tier2")
# -> 25 rows back, exact match

query_slice(arima_1h_df, ["day_of_week"], {"ci_coverage": ("hit", "mean")})
#   day_of_week    n  ci_coverage
#        friday  168     0.928571
#        monday  180     0.927778
#      thursday  195     0.917949
#       tuesday  179     0.932961
#     wednesday  189     0.941799
```

That grouped result was independently checked against a hand-written
pandas `groupby("day_of_week")["hit"].agg(["mean","count"])` on the same
raw rows and matched exactly, to floating-point precision.

## The naive baseline check — an honest negative result

```python
from vinu_initial_analysis.angles.arima.naive_baseline import run_naive_baseline

naive_df = run_naive_baseline("AAPL", "1D", bars)
```

| Timeframe | naive RMSE | naive MAE | ARIMA RMSE | ARIMA MAE | ARIMA better? |
|---|---|---|---|---|---|
| 1D | 6.497 | 4.610 | 6.907 | 4.931 | No |
| 4H | 3.791 | 2.343 | 3.937 | 2.459 | No |
| 1H | 1.812 | 1.175 | 1.845 | 1.233 | No |

On real AAPL data over this real 6-month window, ARIMA's point forecast
did not beat "predict no change" on RMSE/MAE, at any of the three
timeframes checked. This is recorded as-is — it's a real result the
design doc's own rationale anticipated as a live possibility ("ARIMA can
look good on paper while barely beating a model that just predicts 'next
price = last price'"), not a failure of the implementation. ARIMA's own
CI-coverage (80-94% across timeframes, see table above) is a genuinely
different and separately useful signal from its point-forecast accuracy —
a model can have a well-calibrated *interval* while its *point* forecast
is no better than naive, and that's exactly what happened here.

## Related files

- `01-implementation.md` — how this was built, tested, and the 3 real
  bugs found and fixed along the way.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` —
  the checklist this scenario satisfies.
- `../Agents.md` — "Real data source and validation window" / "Two-phase
  timeframe checking" — the decided real-data policy this followed.
