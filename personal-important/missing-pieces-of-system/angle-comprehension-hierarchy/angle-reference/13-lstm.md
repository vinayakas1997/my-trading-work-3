# lstm — LSTM Sequential Forecast

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch single-layer LSTM (method 19 of the 32-method
plan) — the classical recurrent baseline among the six
trained-from-scratch architectures the source survey found competitive
on finance. Processes a rolling close-price window step-by-step through
gated memory cells, fit via a handful of Adam epochs at request time,
producing a one-step point forecast thresholded to a direction.

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
      "forecast_price": 188.70,
      "forecast_return_pct": 0.009,
      "direction": "up",
      "training_window_count": 252,
      "final_training_loss": 0.0047
    }
  ]
}
```

## Condensed glossary blurb (draft)

*The classical recurrent neural baseline (single-layer LSTM) among this
system's from-scratch models — a well-known architecture, treat roughly
as a competent generalist forecaster, not the strongest or weakest of
its cluster.* (~35 words)
