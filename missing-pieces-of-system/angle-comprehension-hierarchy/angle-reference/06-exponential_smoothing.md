# exponential_smoothing — Exponential Smoothing Classical Baseline

**Cluster:** A — Classical statistical forecasts

## Purpose (verbatim from `angles.yaml`)

Double exponential smoothing (Holt's linear trend method) forecast — the
classical, essentially-free statistical baseline (method 28 of the
32-method plan). Weights recent close-price observations more heavily
than older ones via an exponentially-decaying scheme, fitting a level +
trend decomposition (no seasonal component — daily-bar equity series
have no reliable fixed seasonal period) and reporting the one-step-ahead
point forecast alongside the fitted level/trend components.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** One-step-ahead point forecast, fitted
  smoothing parameters (alpha, beta), and level/trend decomposition.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_price": 188.50,
      "alpha": 0.32,
      "beta": 0.08,
      "level": 187.90,
      "trend": 0.15
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A classical, "essentially free" statistical baseline — weights recent
prices more than old ones, fits a simple level+trend. No seasonal
component (daily equity data has none). Treat as a cheap sanity-check
baseline, not a sophisticated signal.* (~35 words)
