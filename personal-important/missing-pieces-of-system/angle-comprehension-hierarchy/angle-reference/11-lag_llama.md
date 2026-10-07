# lag_llama — Lag-Llama Probabilistic Time-Series Model (fallback proxy)

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Probabilistic (multi-quantile) forecast in the spirit of Lag-Llama
(method 16 of the 32-method plan). Lag-Llama has no PyPI package and
only a manual-clone research repo — this angle uses an honestly-labeled
AR(5) linear-Gaussian fallback proxy that still emits a genuinely
probabilistic output.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Point forecast plus a 5-quantile
  (p5/p25/p50/p75/p95) distributional forecast for the next 5 periods,
  plus `model_backend` (always "fallback_proxy") and `fallback_reason`.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "point_forecast": 188.0,
      "p5": 182.1, "p25": 185.6, "p50": 188.0, "p75": 190.4, "p95": 194.2,
      "model_backend": "fallback_proxy",
      "fallback_reason": "lag-llama has no installable package; using AR(5) linear-Gaussian proxy"
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Important: `model_backend` is ALWAYS "fallback_proxy" for this angle —
the real Lag-Llama model was never installable here, so this is a
simple AR(5) statistical substitute, not the actual published model.
Weigh accordingly, lower confidence than a genuinely pretrained angle.*
(~45 words)
