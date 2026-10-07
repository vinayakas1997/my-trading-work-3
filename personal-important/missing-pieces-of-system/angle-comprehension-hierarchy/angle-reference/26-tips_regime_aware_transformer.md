# tips_regime_aware_transformer — TIPS Regime-Aware Transformer Forecast

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch regime-aware transformer (method 24 of the
32-method plan) — detects the current regime (momentum vs.
mean-reversion, via trailing lag-1 return autocorrelation) and
synthesizes a regime-tuned inductive prior by routing a shared
transformer encoder's pooled representation through one of two
regime-specific linear output heads. Produces a one-step point forecast
conditioned on, and an auxiliary label for, the detected regime.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead forecast price/return,
  thresholded direction (up/down/flat), detected regime label
  (momentum/mean_reversion) and its underlying autocorrelation
  statistic, the regime mix seen during training, and the fit's
  training-window count and final training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_price": 189.2,
      "direction": "up",
      "detected_regime": "momentum",
      "regime_autocorrelation": 0.18,
      "training_regime_mix": {"momentum": 0.55, "mean_reversion": 0.45},
      "training_window_count": 252,
      "final_training_loss": 0.0044
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Its own name is misleading — "TIPS" here is this angle's internal
codename, not the inflation-protected bond. It self-detects momentum
vs. mean-reversion regime (via lag-1 autocorrelation) and forecasts
differently depending which — related but distinct from the separate
`regime_analysis` angle's 4-regime classifier.* (~45 words)
