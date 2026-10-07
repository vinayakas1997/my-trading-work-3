# lpatchtst — LPatchTST LSTM+PatchTST Hybrid Forecast

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch LPatchTST model (method 23 of the 32-method plan) —
the best-performing of the six trained-from-scratch architectures in the
source survey (57.7% directional accuracy per arXiv:2603.01820, Sharpe
2.31-2.32). "L" is LSTM, not "lightweight": an LSTM branch and a
patch-transformer branch (the same `PatchEncoderBranch` used standalone
by `patchtst`) each encode the close-price lookback window, their
representations are concatenated, and one linear head produces the
one-step point forecast.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead forecast price/return,
  thresholded direction (up/down/flat), LSTM/patch branch configuration,
  and the fit's training-window count and final training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_price": 189.4,
      "forecast_return_pct": 0.019,
      "direction": "up",
      "lstm_hidden_size": 64,
      "patch_len": 16,
      "training_window_count": 252,
      "final_training_loss": 0.0039
    }
  ]
}
```

## Condensed glossary blurb (draft)

*The single best-performing trained-from-scratch model in this system's
own benchmark survey (57.7% directional accuracy, Sharpe ~2.3) — an
LSTM + patch-transformer hybrid. Among Cluster B, this is one to weight
somewhat more, not equally with the weaker performers.* (~40 words)
