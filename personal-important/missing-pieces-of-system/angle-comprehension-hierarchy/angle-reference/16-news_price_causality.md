# news_price_causality — News-Price Causality

**Cluster:** F — Cross-asset & causality

## Purpose (verbatim from `angles.yaml`)

Statistical proof of news impact on price — Granger causality, Pearson
correlation, lag analysis, event study.

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
      "granger_causality_p_value": 0.032,
      "pearson_correlation": 0.41,
      "optimal_lag_days": 1,
      "event_study_avg_abs_move_pct": 0.018
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Tests whether news genuinely *causes* this symbol's price moves
(Granger causality), not just correlates — a low `granger_causality_p_value`
means real statistical evidence, not just "news and price both moved."
Distinct from sentiment scoring elsewhere in the system.* (~40 words)
