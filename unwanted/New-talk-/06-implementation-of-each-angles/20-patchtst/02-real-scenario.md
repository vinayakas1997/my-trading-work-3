---
name: patchtst-real-scenario
status: phase-1-done
purpose: one concrete, real example proving PatchTST's walk-forward backtest actually works, and the real measured ablation comparison against lpatchtst on identical data.
---

# 20 — patchtst — Real Scenario

125 real AAPL daily bars (Alpaca, same dataset as every other Phase-1
`1D` check this session).

## The call

```python
from vinu_initial_analysis.angles.patchtst.backtest import run_patchtst_backtest

df = run_patchtst_backtest("AAPL", "1D", bars, data_root)  # 25 rows, 4.83s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "bar_ts": 1766966400, "step_index": 0,
  "session": "closed", "subsession": null,
  "day_of_week": "monday", "week_of_month": 5, "month": 12, "quarter": 4,
  "status": "ok", "n_observations": 100, "n_train_windows": 68,
  "lookback": 32, "patch_len": 8, "n_patches": 7,
  "last_close": 273.28,
  "forecast_price": 274.0708, "forecast_return": 0.00289, "direction": "up",
  "train_loss": 0.0171,
  "actual_price": 272.54, "actual_return": -0.00271,
  "hit": 0, "close_sq_error": 2.343, "close_abs_error": 1.531,
  "weights_ref": "AAPL/patchtst/1D/2025/202512/1766966400.pt"
}
```

## Proving the weights are real

```python
store = WeightsStore(data_root)
state_dict = store.load("AAPL/patchtst/1D/2025/202512/1766966400.pt")
# keys: ['branch.pos', 'branch.embed.weight', 'branch.embed.bias',
#        'branch.encoder.layers.0.self_attn.in_proj_weight', ...,
#        'head.weight', 'head.bias']
```

A real trained transformer encoder's full parameter set — matching
`_build_model`'s actual patch-encoder-only architecture exactly (no LSTM
branch, unlike lpatchtst's saved weights).

## Storage + query round-trip, for real

```python
storage.write("AAPL", "patchtst", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "patchtst", granularity="1D", tier="tier2")
# zero column mismatches

query_slice(back, ["day_of_week"], {"avg_hit_rate": ("hit", "mean")})
#  day_of_week  n  avg_hit_rate
#       friday  5          0.60
#       monday  5          0.40
#     thursday  4          0.25
#      tuesday  6          0.50
#    wednesday  5          0.40
```

## The real number: the ablation comparison this angle exists for

| | Directional accuracy | RMSE |
|---|---|---|
| patchtst (patch encoder alone) | **44%** | 5.28 |
| lpatchtst (LSTM + patch hybrid) | 48% | 11.52 |
| Corrected paper benchmark (patchtst) | 54.1% | — |
| Corrected paper benchmark (lpatchtst) | 57.7% | — |

On this real, small (25-step) sample, lpatchtst's hit rate edges out
plain patchtst's by 4 points — directionally consistent with the source
paper's own stated finding that patch segmentation alone is insufficient
without temporal state encoding, though a 4-point gap on 25 steps isn't
strong standalone evidence. Both fall short of their respective paper
benchmarks on this small, single-symbol, different-asset-universe sample
— the same honest pattern recorded for every trained-from-scratch angle
checked this session.

## Related files

- `01-implementation.md` — how this was built and tested.
- `../13-lpatchtst/02-real-scenario.md` — the directly comparable real result on identical data.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
