# regime_analysis — Regime Analysis

**Cluster:** D — Regime & trend structure

## Purpose (verbatim from `angles.yaml`)

4-regime classifier (bull/bear/high_vol/sideways), transition matrix,
per-regime Sharpe ratio.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D, 1W, 1M
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** "Angle-specific results" (catalog
  gives no field-level schema — the fake example below is built from
  the `purpose` field's real description instead; note that
  `trade_plan_authoring.py::fetch_current_regime` reads a real row with
  `metric="current_regime"` and a `regime` field from this angle,
  confirming at least those two field names are real).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "metric": "current_regime",
      "regime": "bull",
      "regime_probabilities": {"bull": 0.62, "bear": 0.08, "high_vol": 0.15, "sideways": 0.15},
      "per_regime_sharpe": {"bull": 1.4, "bear": -0.6, "high_vol": 0.1, "sideways": 0.3}
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Classifies the symbol into one of 4 real regimes (bull/bear/high_vol/
sideways) right now, plus how it's historically performed in each. This
is the same regime the real `trade_plan_authoring.py` uses to tilt
position sizing — a genuinely load-bearing angle, not decorative.* (~45 words)
