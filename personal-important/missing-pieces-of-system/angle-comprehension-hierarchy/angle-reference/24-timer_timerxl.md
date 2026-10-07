# timer_timerxl — Timer / Timer-XL Patch-Based Foundation Model

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Patch-based forecast using the real Timer pretrained model (method 15 of
the 32-method plan) — THUML's `thuml/timer-base-84m` (84M params), a
decoder-only causal transformer pretrained on 260B time points, patch
length 96. Weights are downloaded into the shared models dir (`make
models`). Falls back to an honestly-labeled patch-based statistical
proxy (per-patch mean log-return trend extrapolation) only if the
weights or load are unavailable at runtime. (Corrected 2026-08 — this
entry previously wrongly claimed no installable package existed.)

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Point forecast for the next 5 periods
  (the real model's native output) plus a post-hoc p10/p90
  residual-normal band (not native model uncertainty),
  checkpoint/patch_size/n_patches, `model_backend` ("pretrained" in the
  normal case, "fallback_proxy" only if real inference fails at
  runtime) and `fallback_reason`.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_5": [188.4, 188.9, 189.3, 189.8, 190.2],
      "p10": 184.5, "p90": 192.0,
      "checkpoint": "thuml/timer-base-84m",
      "patch_size": 96,
      "n_patches": 4,
      "model_backend": "pretrained",
      "fallback_reason": null
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A real pretrained foundation model (84M params, 260B time points) in
the normal case — unlike its p10/p90 band, which is a post-hoc
statistical add-on, not the model's own genuine uncertainty (contrast
with `timesfm`, whose deciles ARE native model output).* (~40 words)
