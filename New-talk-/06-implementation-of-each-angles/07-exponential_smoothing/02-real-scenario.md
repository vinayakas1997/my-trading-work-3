---
name: exponential_smoothing-real-scenario
status: phase-1-done
purpose: one concrete, real example proving exponential_smoothing's walk-forward backtest actually works.
---

# 07 — exponential_smoothing — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for ARIMA/
backtesting_44_metrics/drawdown_deep_dive's `1D` Phase 1 checks.

## The call

```python
from vinu_initial_analysis.angles.exponential_smoothing.backtest import run_es_backtest

df = run_es_backtest("AAPL", "1D", bars)  # 25 rows, 0.91s total
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 100,
  "forecast": 307.8197, "alpha": 0.9339, "beta": 0.0,
  "level": 307.4862, "trend": 0.3335, "sse": 2309.29,
  "predicted_direction": "down", "actual_price": 312.73, "actual_direction": "up",
  "hit": 0, "abs_error": 4.91, "squared_error": 24.11
}
```

A real miss here — predicted down, actual moved up. `alpha=0.93` (heavy
weight on the most recent observation) and `beta=0.0` (no real trend
component detected in this particular 100-day window) are genuine fitted
values, not placeholders.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "exponential_smoothing", df, granularity="1D", tier="tier2")
# -> run_id "f6c45eb2a18a", read back: 25 rows, exact match

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  4          0.25
#       monday  5          0.60
#     thursday  6          0.50
#      tuesday  5          0.60
#    wednesday  5          0.40
```

Matched a hand-computed pandas `groupby("day_of_week")["hit"].agg(["mean","count"])`
exactly.

## Naive baseline comparison (real data)

| | RMSE |
|---|---|
| naive | 6.4969 |
| exponential_smoothing | 6.6719 |

Naive wins again — same honest pattern already seen with ARIMA and
Chronos on this identical real AAPL window. Overall directional accuracy
48% — essentially coin-flip on this small real sample.

## Related files

- `01-implementation.md` — how this was built and tested.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
