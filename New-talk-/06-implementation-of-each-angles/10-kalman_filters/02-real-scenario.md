---
name: kalman_filters-real-scenario
status: phase-1-done
purpose: one concrete, real example proving kalman_filters' walk-forward backtest actually works, and that the filtered/smoothed separation is genuinely enforced.
---

# 10 — kalman_filters — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for every other
Phase-1 `1D` check this session.

## The call

```python
from vinu_initial_analysis.angles.kalman_filters.backtest import run_kalman_backtest

df = run_kalman_backtest("AAPL", "1D", bars)  # 25 rows, 1.33s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 100,
  "filtered_level": 307.5877, "filtered_level_std": 1.1485,
  "filtered_trend": 0.4805, "filtered_trend_std": 0.6464,
  "predicted_direction": "up", "actual_price": 312.73, "actual_direction": "up",
  "hit": 1
}
```

`smoothed_level`/`smoothed_trend` are not present in this row at all —
confirmed by checking `df.columns` directly, not just by not printing
them.

## The whole-history-only smoothed diagnostic, separately

```python
from vinu_initial_analysis.angles.kalman_filters.backtest import run_smoothed_diagnostic

smoothed = run_smoothed_diagnostic("AAPL", "1D", bars)
# {'symbol': 'AAPL', 'timeframe': '1D', 'status': 'ok', 'n_observations': 125,
#  'smoothed_level': 313.29, 'smoothed_trend': 0.3128}
```

One row, no tags, no `bar_ts` — the hindsight "ground truth" view, kept
structurally separate from the causal backtest above.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "kalman_filters", df, granularity="1D", tier="tier2")
# -> run_id "0315771c2362", read back: 25 rows, exact match

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  4      0.500000
#       monday  5      0.600000
#     thursday  6      0.666667
#      tuesday  5      0.600000
#    wednesday  5      0.600000
```

Matched a hand-computed pandas `groupby` exactly.

## Naive baseline comparison (real data) — the first angle to actually win

| | Directional accuracy |
|---|---|
| naive (persistence) | 52% |
| kalman_filters | **60%** |

Every prior Group A angle checked this session (ARIMA, Chronos,
exponential_smoothing, iTransformer) lost to its naive comparison on this
same real AAPL window. This is the first one that beat it — recorded as
a real, positive result on one small sample, not overstated as proof of
genuine skill.

## Related files

- `01-implementation.md` — how this was built and tested, including the naive-baseline decision.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
