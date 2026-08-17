---
name: tft-real-scenario
status: phase-1-done
purpose: one concrete, real example proving TFT's walk-forward backtest actually works, including its real, non-crossing quantile band and variable-selection interpretability output.
---

# 26 — tft — Real Scenario

125 real AAPL daily bars (Alpaca, same dataset as every other Phase-1
`1D` check this session).

## The call

```python
from vinu_initial_analysis.angles.tft.backtest import run_tft_backtest

df = run_tft_backtest("AAPL", "1D", bars, data_root)  # 25 rows, 6.76s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1766966400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "monday", "week_of_month": 5, "month": 12, "quarter": 4,
  "status": "ok", "n_observations": 100, "n_train_windows": 49, "lookback": 30,
  "last_close": 273.28,
  "forecast_price_p10": 263.96, "forecast_price_p50": 269.70, "forecast_price_p90": 275.68,
  "direction": "down",
  "variable_selection_weights": {
    "ret_1": 0.1973, "ret_5": 0.1124, "sma_ratio_5": 0.1416,
    "sma_ratio_21": 0.1488, "vol_5": 0.2446, "high_low_range": 0.1551
  },
  "train_loss": 0.00339,
  "actual_price": 272.54, "actual_return": -0.00271,
  "hit": 1, "in_band": 1,
  "pinball_loss": {"0.1": 0.858, "0.5": 1.419, "0.9": 0.314},
  "close_sq_error": 8.051, "close_abs_error": 2.837,
  "weights_ref": "AAPL/tft/1D/2025/202512/1766966400.pt"
}
```

`forecast_price_p10 (263.96) <= p50 (269.70) <= p90 (275.68)` — verified
non-crossing on every real backtest row, not just assumed from the
architecture. `variable_selection_weights` sums to ~1.0 (real softmax
output) — `vol_5` and `ret_1` dominated this particular step.

## Proving the weights are real

```python
store = WeightsStore(data_root)
state_dict = store.load("AAPL/tft/1D/2025/202512/1766966400.pt")
# keys: ['var_select.gate.0.weight', 'var_select.gate.0.bias',
#        'lstm.weight_ih_l0', 'lstm.weight_hh_l0', ...,
#        'attn.in_proj_weight', 'attn.out_proj.weight',
#        'median_head.weight', 'delta_head.weight', ...]
```

A real trained variable-selection gate + LSTM + multi-head attention +
median/delta heads — matching `_build_model`'s actual TFT-lite
architecture exactly.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "tft", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "tft", granularity="1D", tier="tier2")
# zero column mismatches

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean"), "avg_coverage": ("in_band", "mean")})
#  day_of_week  n  avg_hit_rate  avg_coverage
#       friday  5          0.20      0.000000
#       monday  5          0.40      0.800000
#     thursday  4          0.25      1.000000
#      tuesday  6          0.50      0.666667
#    wednesday  5          0.40      1.000000
```

## The real number, checked against the corrected paper benchmark

| | Value |
|---|---|
| Corrected paper benchmark (arXiv:2603.01820) | 58.4% hit rate, Sharpe 2.20 |
| This backtest's measured directional accuracy (P50) | **36%** |
| This backtest's measured CI-coverage ([P10,P90], nominal 80%) | **68%** |
| naive baseline RMSE / MAE | 3.80 / 2.61 |
| TFT RMSE / MAE (P50) | 5.08 / 4.10 |

Below the paper's figure on this real, small (25-step), single-symbol
sample, both on directional accuracy and CI-coverage — naive beat it on
RMSE/MAE too. Recorded plainly, same convention as every other
trained-from-scratch angle's real finding this session: the paper's own
benchmark universe (futures, 2010-2025) differs from this project's
equity/date range, a caveat the design doc itself already names, so this
is an honest report of what this specific small real check measured, not
a refutation of the paper.

## Related files

- `01-implementation.md` — how this was built and tested.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
