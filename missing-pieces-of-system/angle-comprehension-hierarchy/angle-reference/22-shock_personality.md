# shock_personality — Shock Personality

**Cluster:** E — Shock / personality behavior

## Purpose (verbatim from `angles.yaml`)

Post-shock behavioral characterization — `gap_fill_rate`,
`vol_persistence` (real GARCH, `vinu_tools.compute.risk.volatility`),
`drift_persistence_days` (sign-streak) and `drift_mean_autocorr` (mean
lag-1-9 return autocorrelation), each also split by news presence
(`has_news`/`nearest_news_days`). Every field includes sample size and
confidence interval.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Shock personality results with
  confidence intervals. Confirmed real fields from
  `trade_plan_authoring.py::fetch_personality_features`/
  `_build_signal_ledger`: `gap_fill_rate` (a dict with `mean`),
  `vol_persistence`.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "gap_fill_rate": {"mean": 0.62, "n": 18, "ci": [0.44, 0.78]},
      "vol_persistence": 0.91,
      "drift_persistence_days": {"mean": 2.3, "n": 18},
      "drift_mean_autocorr": {"mean": 0.11, "n": 18},
      "has_news": true,
      "nearest_news_days": 0
    }
  ]
}
```

## Condensed glossary blurb (draft)

*This symbol's own historical reaction pattern to shocks — real,
load-bearing angle (one of the original two the forecast prompt read
exclusively before 2026-09-14, per this system's own audit history).
High `gap_fill_rate` means gaps here tend to close; high
`vol_persistence` means volatility regimes here are sticky, not
mean-reverting.* (~50 words)
