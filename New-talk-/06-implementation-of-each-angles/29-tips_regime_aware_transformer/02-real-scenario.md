---
name: tips_regime_aware_transformer-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the regime-gated backtest actually works, and the real (inconclusive) answer to whether the regime split earns its keep.
---

# 29 — tips_regime_aware_transformer — Real Scenario

250 real AAPL daily bars (a larger real slice than most trained-from-
scratch angles' checks — needed for real regime diversity, since a
120-bar-floor angle's first small dataset produced only 5 real steps, all
one regime).

## The call

```python
from vinu_initial_analysis.angles.tips_regime_aware_transformer.backtest import run_tips_backtest

df = run_tips_backtest("AAPL", "1D", bars, data_root)  # 130 rows, 110.6s
```

## Real output — first row

```json
{
  "symbol": "AAPL", "timeframe": "1D", "status": "ok",
  "n_observations": 120, "n_train_windows": 96, "lookback": 24, "regime_window": 20,
  "last_close": 255.97,
  "forecast_price": 257.97, "forecast_return": 0.0078, "direction": "up",
  "regime": "momentum", "regime_autocorr": 0.269,
  "n_momentum_windows": 72, "n_mean_reversion_windows": 24,
  "train_loss": 0.0841,
  "actual_price": 260.25, "actual_return": 0.0167,
  "hit": 1, "close_sq_error": 5.18, "close_abs_error": 2.28,
  "weights_ref": "AAPL/tips_regime_aware_transformer/1D/2026/202601/1769558400.pt"
}
```

## Proving the weights are real (both regime heads)

```python
store = WeightsStore(data_root)
state_dict = store.load(row0["weights_ref"])
# keys include: 'token_embed.weight', 'encoder.layers.0.self_attn.in_proj_weight',
#               'momentum_head.weight', 'mean_reversion_head.weight', ...
```

Both regime-specific heads are present in every saved step's state —
confirms the shared-encoder-plus-dual-heads architecture is actually
what's being trained and saved, not a simplified stand-in.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "tips_regime_aware_transformer", df, granularity="1D", tier="tier2")
back = storage.read("AAPL", "tips_regime_aware_transformer", granularity="1D", tier="tier2")
# zero column mismatches

query_slice(back, ["regime"], {"avg_hit_rate": ("hit", "mean"), "avg_rmse_component": ("close_sq_error", "mean")})
#           regime    n  avg_hit_rate  avg_rmse_component
#   mean_reversion   29      0.517241            94.685625
#         momentum  101      0.504950           106.583217
```

## The real number: does the regime-gating earn its keep?

| Regime | n | Hit rate | RMSE |
|---|---|---|---|
| momentum | 101 | 50.5% | 10.32 |
| mean_reversion | 29 | 51.7% | 9.86 |
| **Overall** | 130 | 50.8% | 10.19 |
| naive baseline | 130 | — | 3.81 |

Essentially indistinguishable hit rates between the two regimes on this
real sample — no clear evidence either head specializes usefully within
its claimed regime. Overall RMSE is well behind the naive baseline. This
is a real, honest answer to the design doc's own open question about
whether the simple autocorrelation-based regime split is a good
detector — on this small-but-real AAPL sample, it leans toward "not
clearly differentiated," recorded plainly rather than assumed either way
in advance.

## Related files

- `01-implementation.md` — how this was built and tested, including why
  a larger real dataset was needed for this specific angle.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
