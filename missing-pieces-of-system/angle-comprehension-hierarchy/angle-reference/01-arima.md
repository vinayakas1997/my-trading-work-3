# arima — ARIMA Classical Statistical Baseline

**Cluster:** A — Classical statistical forecasts

## Purpose (verbatim from `angles.yaml`)

AutoRegressive Integrated Moving Average forecast — the classical
statistical baseline (method 25 of the 32-method plan). Fits an
ARIMA(p, d, q) model to the close-price series with order chosen by AIC
grid search, no fixed lookback window, and reports the model's standard
output shape: a one-step-ahead point forecast plus its 95% confidence
interval.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Fitted ARIMA order, AIC, one-step-ahead
  point forecast, and 95% confidence interval.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only, matching the real output shape above.
> Never treat this as an actual AAPL (or any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "order": [2, 1, 1],
      "aic": 845.32,
      "forecast_price": 187.42,
      "forecast_ci_lower": 182.10,
      "forecast_ci_upper": 192.74
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A classical statistical time-series forecast (ARIMA), not a neural
model — fits trend/autocorrelation patterns in recent closes. Read its
`forecast_price` as a simple, interpretable baseline, not a
sophisticated one; its 95% interval is its own honest uncertainty
estimate.* (~40 words)
