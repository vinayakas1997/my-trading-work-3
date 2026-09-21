# garch — GARCH Volatility Forecast

**Cluster:** C — Volatility & drawdown risk

## Purpose (verbatim from `angles.yaml`)

Standalone GARCH(1,1) conditional-variance forecast — the classical,
zero-footprint volatility baseline (method 26 of the 32-method plan).
Extracted from `shock_personality`, which already fits GARCH internally
for its own `vol_persistence` field (via
`vinu_tools.compute.risk.volatility.garch_volatility`) — this angle
exposes the same underlying fit as its own first-class result rather
than duplicating the math.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Forecasted next-period volatility plus
  fitted GARCH(1,1) parameters.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "forecast_volatility": 0.024,
      "omega": 0.000012,
      "alpha": 0.09,
      "beta": 0.88,
      "persistence": 0.97
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Standard GARCH(1,1) — forecasts next-period volatility, not direction.
High `persistence` (alpha+beta close to 1) means today's volatility
regime is likely to keep going, not mean-revert quickly. Same underlying
fit `shock_personality` uses internally.* (~35 words)
