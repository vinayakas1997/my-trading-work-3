# trend_session_structure — Trend Session Structure

**Cluster:** D — Regime & trend structure

## Purpose (verbatim from `angles.yaml`)

Session-level analysis of `trend_lifecycle` peaks/troughs — which
trading session (premarket/regular/afterhours) produces reliable tops,
with per-session drawdown, recovery, and match-similarity statistics.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H (note: no 1D — this angle
  is inherently intraday, since it distinguishes premarket/regular/
  afterhours sessions, which collapse into one bar at the 1D timeframe)
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
      "reliable_top_session": "regular",
      "session_stats": {
        "premarket": {"drawdown_pct": -0.04, "recovery_days": 3, "match_similarity": 0.61},
        "regular": {"drawdown_pct": -0.09, "recovery_days": 8, "match_similarity": 0.82},
        "afterhours": {"drawdown_pct": -0.02, "recovery_days": 2, "match_similarity": 0.47}
      }
    }
  ]
}
```

## Condensed glossary blurb (draft)

*A direct extension of `trend_lifecycle` — takes the same peak/trough
patterns and asks WHICH intraday session (premarket/regular/afterhours)
they actually happen in. Intraday-only (not available at the 1D
timeframe). Reads best paired with `trend_lifecycle`, not standalone.*
(~40 words)
