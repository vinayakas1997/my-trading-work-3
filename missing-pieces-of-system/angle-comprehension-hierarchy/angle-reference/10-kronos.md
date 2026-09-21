# kronos — Kronos Financial K-Line Foundation Model

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Next-K-line forecast using the real Kronos pretrained model (method 9 of
the 32-method plan) — the flagship open-source financial K-line
foundation model (AAAI 2026), a tokenizer + autoregressive decoder-only
transformer pretrained on 12B K-line records from 45 exchanges. Weights
+ tokenizer are downloaded into the shared models dir (`make models`);
falls back to an honestly-labeled in-process-trained MLP proxy only if
the weights or load are unavailable at runtime.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Predicted next-bar OHLC plus a 5-step
  OHLC forecast, `model_backend` ("pretrained" or "fallback_proxy") and
  `fallback_reason` explaining why.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "next_open": 187.8, "next_high": 189.2, "next_low": 186.9, "next_close": 188.5,
      "forecast_5step": [188.5, 189.0, 189.4, 189.9, 190.3],
      "model_backend": "pretrained",
      "fallback_reason": null
    }
  ]
}
```

## Condensed glossary blurb (draft)

*The flagship finance-specific foundation model here — pretrained on
12B real K-line records from 45 exchanges, this system's closest thing
to a "first-choice" deep-learning signal (unlike `chronos`/`timesfm`,
which are general-purpose comparison baselines). Check `model_backend`:
if "fallback_proxy," this is a weaker MLP substitute, not the real
model.* (~50 words)
