# timesfm — TimesFM Time-Series Foundation Model

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Zero-shot point + quantile forecast from Google's TimesFM foundation
model (method 11 of the 32-method plan). General-purpose, not
finance-specific — a comparison baseline alongside Chronos and Kronos,
not a first-choice signal.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Point forecast plus all 9 real decile
  levels (q10 through q90 — the model's own trained quantile-head
  output, genuine model confidence, not a bolted-on statistical band)
  for the next 5 periods, plus `context_length_used`, `model_backend`
  ("pretrained" via google/timesfm-2.5-200m-pytorch, or "fallback_proxy"
  if the real checkpoint could not be loaded) and `fallback_reason`.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "point_forecast": 188.6,
      "q10": 183.1, "q20": 184.8, "q30": 186.0, "q40": 187.3, "q50": 188.6,
      "q60": 189.9, "q70": 191.2, "q80": 192.6, "q90": 194.0,
      "context_length_used": 512,
      "model_backend": "pretrained"
    }
  ]
}
```

## Condensed glossary blurb (draft)

*General-purpose (not finance-specific) — a comparison baseline like
`chronos`, not this system's first-choice signal. Its 9 deciles ARE the
model's genuine trained uncertainty output, not a post-hoc statistical
band (contrast with `timer_timerxl`'s p10/p90, which is bolted-on).*
(~40 words)
