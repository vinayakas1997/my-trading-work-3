# chronos — Chronos Time-Series Foundation Model

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Zero-shot probabilistic forecast from Amazon's Chronos-T5 time-series
foundation model (method 10 of the 32-method plan). General-purpose, not
finance-specific — a comparison baseline against Kronos, not a
first-choice signal (general TSFMs tend to underperform finance-specific
models on K-line data).

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Quantile forecast (p10/median/p90) for
  the next 5 periods, plus `model_backend` ("pretrained" via
  amazon/chronos-t5-large, or "fallback_proxy" if the real pipeline
  could not be loaded).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "p10": [186.1, 185.4, 184.9, 184.2, 183.8],
      "median": [188.0, 188.6, 189.1, 189.5, 190.0],
      "p90": [189.9, 191.5, 193.0, 194.4, 195.7],
      "model_backend": "pretrained"
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A general-purpose (not finance-specific) probabilistic forecasting
model — a comparison baseline, explicitly not this system's
first-choice signal. Read its p10/median/p90 spread as a rough
uncertainty band, and weight it below finance-specific angles like
`kronos`.* (~35 words)
