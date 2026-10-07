# moirai — MOIRAI Any-Variate Time-Series Foundation Model (fallback proxy)

**Cluster:** B — Deep-learning / foundation-model forecasts

## Purpose (verbatim from `angles.yaml`)

Forecast in the spirit of Salesforce's MOIRAI (method 13 of the
32-method plan). The real `uni2ts` package exists but would downgrade
the shared environment's torch build and can't exercise MOIRAI's
any-variate multi-ticker mechanism from this per-symbol interface
anyway — this angle uses an honestly-labeled AR(3) statistical fallback
proxy.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Point + p10/p90 forecast for the next
  5 periods, plus `model_backend` (always "fallback_proxy"),
  `fallback_reason`, and `any_variate_note` explaining the single-ticker
  degeneration.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "point_forecast": 187.9,
      "p10": 183.2, "p90": 192.6,
      "model_backend": "fallback_proxy",
      "fallback_reason": "uni2ts would downgrade shared torch build",
      "any_variate_note": "degenerated to single-ticker AR(3); MOIRAI's real multi-ticker mechanism not exercised"
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Always a "fallback_proxy" here (simple AR(3)), never the real MOIRAI
model — and even the real model's key feature (attending across
multiple tickers at once) can't work through this system's per-symbol
interface anyway. Weight this low, closer to a generic statistical
baseline than a foundation model.* (~45 words)
