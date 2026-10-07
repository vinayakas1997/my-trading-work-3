# trend_lifecycle — Trend Lifecycle

**Cluster:** D — Regime & trend structure

## Purpose (verbatim from `angles.yaml`)

Peak/trough pattern library, KNN similarity matching, trend stage
classification, reversal signals with percentage exit thresholds.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D, 1W
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** "Angle-specific results" (catalog
  gives no field-level schema; the fake example below is built from the
  `purpose` field, plus `trade_plan_authoring.py::fetch_angle_signals`,
  which confirms a real row with `type="lifecycle"` and a `stage` field
  whose real observed values include `"uptrend"`/`"downtrend"`).

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "type": "lifecycle",
      "stage": "uptrend",
      "knn_similarity_score": 0.77,
      "nearest_pattern_id": "pattern_042",
      "reversal_signal": false,
      "pct_exit_threshold": 0.06
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Real, load-bearing angle — `stage` directly feeds a real supporting/
contradicting signal in `trade_plan_authoring.py`'s signal ledger.
Matches current price action against a library of historical
peak/trough patterns (KNN) to classify what stage of a trend this
symbol is in right now, and whether a reversal looks imminent.* (~45 words)
