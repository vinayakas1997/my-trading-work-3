# kalman_filters — Kalman Filter State Estimation

**Cluster:** A — Classical statistical forecasts

## Purpose (verbatim from `angles.yaml`)

Classical recursive state-estimation baseline (method 27 of the
32-method plan). Recursively estimates a hidden underlying price level
and local trend from noisy close-price observations via a
predict-then-correct cycle (statsmodels' local-linear-trend structural
time series model — a two-state Kalman filter/smoother). Reports the
present/recent filtered and smoothed state plus its uncertainty (state
covariance) — **not a forward forecast**.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Filtered and smoothed level/trend
  state estimates plus their standard deviations (state covariance
  uncertainty).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "filtered_level": 187.6,
      "filtered_trend": 0.09,
      "level_std": 0.85,
      "trend_std": 0.03
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Important distinction: this is NOT a forecast — it's a denoised
estimate of the symbol's *current* underlying price level and trend
(filters out noise from the raw close series). Use it to read "where is
this really trading right now," not "where is it going."* (~40 words)
