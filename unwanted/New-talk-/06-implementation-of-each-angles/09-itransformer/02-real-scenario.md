---
name: itransformer-real-scenario
status: phase-1-done
purpose: one concrete, real example proving iTransformer's walk-forward backtest actually works, including all 5 channel forecasts now genuinely exposed.
---

# 09 — itransformer — Real Scenario

125 real AAPL daily bars (Alpaca), same dataset used for every other
Phase-1 `1D` check this session.

## The call

```python
from vinu_initial_analysis.angles.itransformer.backtest import run_itransformer_backtest

df = run_itransformer_backtest("AAPL", "1D", bars, data_root)  # 25 rows, 4.43s
```

## Real output — first row, all 5 channels present

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1782950400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "thursday", "week_of_month": 1, "month": 7, "quarter": 3,
  "status": "ok", "n_observations": 100, "n_train_windows": 68, "lookback": 32,
  "channels": "open,high,low,close,volume", "n_channels": 5,
  "last_close": 308.43,
  "forecast_open": 289.48, "forecast_high": 294.41, "forecast_low": 285.33,
  "forecast_close": 289.56, "forecast_volume": 3012247.08,
  "forecast_price": 289.5607, "forecast_return": -0.0612, "direction": "down",
  "train_loss": 0.1352,
  "actual_price": 312.73, "actual_return": 0.0139, "hit": 0,
  "abs_error": 23.17, "squared_error": 536.82,
  "weights_ref": "AAPL/itransformer/1D/2026/202607/1782950400.pt"
}
```

All 5 real channel forecasts — `open`/`high`/`low`/`close`/`volume` — are
genuinely present here, not just `close`. Before this implementation, the
code computed all 5 internally but only ever reported `close`, silently
discarding the rest.

## Proving the weights are real

```python
from vinu_initial_analysis.storage.weights import WeightsStore

store = WeightsStore(data_root)
state_dict = store.load("AAPL/itransformer/1D/2026/202607/1782950400.pt")
# keys: ['embed.weight', 'embed.bias', 'encoder.layers.0.self_attn.in_proj_weight', ...]
```

A real trained transformer's weights — embedding layer, encoder
self-attention, exactly the architecture `_build_model` constructs.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "itransformer", df, granularity="1D", tier="tier2")
# -> run_id "8a8f1edb2072", read back: 25 rows, exact match

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  4      0.500000
#       monday  5      0.400000
#     thursday  6      0.333333
#      tuesday  5      0.400000
#    wednesday  5      0.200000
```

Matched a hand-computed pandas `groupby` exactly.

## Naive baseline comparison (real data)

| | RMSE | Directional accuracy |
|---|---|---|
| naive | 6.4969 | n/a (no meaningful direction) |
| iTransformer | 12.9453 | 36% |

A wider gap than ARIMA/Chronos/exponential_smoothing showed against
naive on this same real window — recorded honestly, not attributed with
confidence to any single cause given the small (25-step, one-symbol)
sample.

## Related files

- `01-implementation.md` — how this was built and tested, including a
  self-caught design inconsistency (naive baseline's hit field) fixed
  before it was ever committed.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
