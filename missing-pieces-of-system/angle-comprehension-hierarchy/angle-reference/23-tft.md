# tft — TFT Temporal Fusion Transformer (Quantile Forecast)

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch, lightweight Temporal Fusion Transformer (method 22
of the 32-method plan) — a gated variable-selection network weights
engineered return/volatility features at each time step, an LSTM encodes
the sequence, self-attention pools it, and three linear heads produce
P10/P50/P90 next-step return quantiles trained jointly via pinball loss.
Known-future inputs and static covariates from the source spec are not
modeled (no such data available from `bars`/`news`).

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** P10/P50/P90 next-step return and
  price quantile forecasts, thresholded direction from the median, the
  last-step variable-selection weights per feature, and the fit's
  training-window count and final training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "p10_price": 185.0, "p50_price": 188.5, "p90_price": 192.1,
      "direction": "up",
      "top_feature": "volatility_20d",
      "variable_selection_weights": {"volatility_20d": 0.34, "return_5d": 0.28, "return_20d": 0.21},
      "training_window_count": 252,
      "final_training_loss": 0.021
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A quantile forecaster that also reports WHICH engineered features drove
its own prediction (`variable_selection_weights`) — the only angle in
this cluster that self-explains its reasoning. A partial, lightweight
version of the real TFT (no known-future/static covariates modeled,
unlike the original spec).* (~45 words)
