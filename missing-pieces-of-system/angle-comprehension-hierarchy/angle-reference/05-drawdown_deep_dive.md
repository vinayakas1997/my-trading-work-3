# drawdown_deep_dive — Drawdown Deep-Dive

**Cluster:** C — Volatility & drawdown risk

## Purpose (verbatim from `angles.yaml`)

Drawdown detection, news attribution, max drawdown duration, recovery
time across multi-timeframe.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** "Angle-specific results" (catalog
  gives no field-level schema — the fake example below is built from
  the `purpose` field's real description instead).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "current_drawdown_pct": -0.05,
      "max_drawdown_pct": -0.22,
      "max_drawdown_duration_days": 34,
      "recovery_time_days": 21,
      "news_attributed_pct": 0.40
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A detailed look at this symbol's real historical drawdowns — how deep,
how long, how fast it recovered, and how much of it news explains.
Backward-looking risk context, not a forecast; use it to calibrate how
much a current move should worry you.* (~40 words)
