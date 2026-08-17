---
name: lpatchtst-real-scenario
status: phase-1-done
purpose: one concrete, real example proving LPatchTST's walk-forward backtest actually works, and the real measured result against the corrected paper benchmark.
---

# 13 — lpatchtst — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for every other
Phase-1 `1D` check this session.

## The call

```python
from vinu_initial_analysis.angles.lpatchtst.backtest import run_lpatchtst_backtest

df = run_lpatchtst_backtest("AAPL", "1D", bars, data_root)  # 25 rows, 6.81s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 100, "n_train_windows": 68,
  "lookback": 32, "lstm_hidden_size": 16, "n_patches": 7,
  "last_close": 308.43,
  "forecast_price": 297.4936, "forecast_return": -0.0355, "direction": "down",
  "train_loss": 0.0470,
  "actual_price": 312.73, "actual_return": 0.0139,
  "hit": 0, "close_sq_error": 232.15, "close_abs_error": 15.24,
  "weights_ref": "AAPL/lpatchtst/1D/2026/202607/1782950400.pt"
}
```

## Proving the weights are real

```python
store = WeightsStore(data_root)
state_dict = store.load("AAPL/lpatchtst/1D/2026/202607/1782950400.pt")
# keys: ['lstm.weight_ih_l0', 'lstm.weight_hh_l0', 'lstm.bias_ih_l0', ...]
```

A real trained LSTM's weight matrices — matching the actual hybrid
architecture (`_build_model`'s LSTM branch + patch branch).

## Storage + query round-trip, for real

```python
storage.write("AAPL", "lpatchtst", df, granularity="1D", tier="tier2")
# -> run_id "05a224585446", read back: 25 rows, exact match

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  4          0.5
#       monday  5          0.6
#     thursday  6          0.5
#      tuesday  5          0.4
#    wednesday  5          0.4
```

Matched a hand-computed pandas `groupby` exactly.

## The real number, checked against the corrected paper benchmark

| | Value |
|---|---|
| Corrected paper benchmark (arXiv:2603.01820) | 57.7% |
| This backtest's measured directional accuracy | **48%** |
| naive baseline RMSE | 6.4969 |
| LPatchTST RMSE | 11.5231 |

Below the paper's figure on this real (small, one-symbol, 25-step)
sample, and naive beat it on RMSE too. Recorded plainly — the paper's own
benchmark is a different asset universe and date range (futures,
2010-2025), a caveat the design doc itself already names, so this isn't
treated as a refutation of the paper, just an honest report of what this
specific, small real check actually measured.

## Related files

- `01-implementation.md` — how this was built and tested.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
