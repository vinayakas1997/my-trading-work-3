---
name: lstm-real-scenario
status: phase-1-done
purpose: one concrete, real example proving LSTM's walk-forward backtest actually works, and the real measured result against the corrected paper benchmark.
---

# 14 — lstm — Real Scenario

125 real AAPL daily bars (Alpaca, aggregated from the project's own cached
1-minute archive+live data — see `01-implementation.md` for the one
corrupt live file worked around to build this set).

## The call

```python
from vinu_initial_analysis.angles.lstm.backtest import run_lstm_backtest

df = run_lstm_backtest("AAPL", "1D", bars, data_root)  # 25 rows, 3.56s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1766966400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "monday", "week_of_month": 5, "month": 12, "quarter": 4,
  "status": "ok", "n_observations": 100, "n_train_windows": 70,
  "lookback": 30, "hidden_size": 16,
  "last_close": 273.28,
  "forecast_price": 273.5184, "forecast_return": 0.000872, "direction": "up",
  "train_loss": 0.04292,
  "actual_price": 272.54, "actual_return": -0.002708,
  "hit": 0, "close_sq_error": 0.9572, "close_abs_error": 0.9784,
  "weights_ref": "AAPL/lstm/1D/2025/202512/1766966400.pt"
}
```

## Proving the weights are real

```python
store = WeightsStore(data_root)
state_dict = store.load("AAPL/lstm/1D/2025/202512/1766966400.pt")
# keys: ['lstm.weight_ih_l0', 'lstm.weight_hh_l0', 'lstm.bias_ih_l0',
#        'lstm.bias_hh_l0', 'head.weight', 'head.bias']
```

A real trained single-layer LSTM's weight matrices plus the linear head —
matching `_build_model`'s actual architecture exactly.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "lstm", df, granularity="1D", tier="tier2")
# -> run_id "cafdeeb24822", read back: 25 rows

back = storage.read("AAPL", "lstm", granularity="1D", tier="tier2")
# back's columns == df's 26 columns + AngleStorage's own metadata columns
# (run_id, angle_name, started_at, analysis_from, analysis_until,
# stored_at) -- confirmed by an explicit column-set diff, not just
# .equals(), since the extra metadata columns make direct .equals() fail
# even though the underlying data round-tripped exactly.

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  5      0.600000
#       monday  5      0.200000
#     thursday  4      0.250000
#      tuesday  6      0.666667
#    wednesday  5      0.400000
```

Matched a hand-computed pandas `groupby` exactly.

## The real number, checked against the corrected paper benchmark

| | Value |
|---|---|
| Corrected paper benchmark (arXiv:2603.01820) | 55.4% |
| This backtest's measured directional accuracy | **44%** |
| naive baseline RMSE / MAE | 3.7955 / 2.6056 |
| LSTM RMSE / MAE | 4.2480 / 3.3295 |

Below the paper's figure on this real (small, one-symbol, 25-step)
sample, and naive beat it on both RMSE and MAE. Recorded plainly — same
caveat as lpatchtst's own real finding: the paper's benchmark universe and
date range differ from this project's, so this is an honest report of
what this specific small real check measured, not a refutation of the
paper.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  real corrupt-parquet-file workaround.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
