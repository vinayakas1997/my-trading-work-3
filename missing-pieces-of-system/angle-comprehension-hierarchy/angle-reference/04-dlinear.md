# dlinear — DLinear Decomposition Linear Forecast

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch DLinear model (method 18 of the 32-method plan) —
the simplest of six architectures the source survey found "actually win
on finance." Decomposes the close-price window into a moving-average
trend and a seasonal residual, fits one small linear layer to each on a
handful of Adam epochs at request time, and sums their outputs into a
one-step-ahead point forecast, thresholded to a direction.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead forecast price/return,
  thresholded direction (up/down/flat), and the fit's training-window
  count and final training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_price": 189.10,
      "forecast_return_pct": 0.012,
      "direction": "up",
      "training_window_count": 252,
      "final_training_loss": 0.0043
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A simple, real (trained-from-scratch, not a big pretrained model)
linear forecast — splits price into trend + seasonal parts, sums them.
Despite its simplicity, the source survey found this genuinely
competitive on finance. Trust it roughly as much as the other
from-scratch models in this cluster.* (~40 words)
