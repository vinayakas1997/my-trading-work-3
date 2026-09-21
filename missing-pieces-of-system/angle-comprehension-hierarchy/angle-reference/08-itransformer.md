# itransformer — iTransformer Cross-Variate Attention Forecast

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch iTransformer model (method 21 of the 32-method
plan) — tokenizes variates (here: this symbol's OHLCV channels, since
the per-symbol `compute()` interface has no sibling-ticker input to
exploit true cross-asset attention) rather than time steps, so
self-attention runs across variate-tokens. Fit via a handful of Adam
epochs at request time; reports the close-channel one-step forecast,
thresholded to a direction.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead forecast for every
  OHLCV channel used as a variate (forecast_open/high/low/close/volume),
  close-channel return thresholded to a direction (up/down/flat), which
  channels were used, and the fit's training-window count and final
  training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_open": 187.9, "forecast_high": 189.4,
      "forecast_low": 187.1, "forecast_close": 188.9, "forecast_volume": 5.4e7,
      "direction": "up",
      "channels_used": ["open", "high", "low", "close", "volume"],
      "training_window_count": 252,
      "final_training_loss": 0.0051
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A transformer that attends across this symbol's own OHLCV channels
(not across other tickers — no true cross-asset attention here despite
the name's promise). Read `direction` from its close-channel forecast;
the other channel forecasts are supporting detail, not independent
signals.* (~40 words)
