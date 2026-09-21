# patchtst — PatchTST Channel-Independent Patch Transformer

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Trained-from-scratch PatchTST model (method 20 of the 32-method plan) —
splits the close-price lookback window into fixed-length patches, embeds
each as a token, and runs a small transformer encoder's self-attention
across patches (channel-independent design, a regularizer per the source
survey). Fit via a handful of Adam epochs at request time; produces a
one-step point forecast thresholded to a direction. See `lpatchtst` for
the LSTM+PatchTST hybrid built on the same shared patch-encoder core.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead forecast price/return,
  thresholded direction (up/down/flat), patch configuration, and the
  fit's training-window count and final training loss.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_price": 189.00,
      "forecast_return_pct": 0.014,
      "direction": "up",
      "patch_len": 16,
      "num_patches": 8,
      "training_window_count": 252,
      "final_training_loss": 0.0041
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A patch-based transformer forecaster (splits price history into
chunks, attends across them). Related to `lpatchtst`, which builds an
LSTM hybrid on this same core — the two aren't fully independent
signals, keep that in mind if both agree.* (~40 words)
