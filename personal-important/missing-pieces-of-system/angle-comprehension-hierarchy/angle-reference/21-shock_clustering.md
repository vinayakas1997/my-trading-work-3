# shock_clustering — Shock Clustering

**Cluster:** E — Shock / personality behavior

## Purpose (verbatim from `angles.yaml`)

Identifies which watchlist peers tend to shock together with this
symbol: co-shock rate (did the peer also register its own shock within
+/-1 trading day) plus shock-day Pearson correlation with a bootstrapped
95% CI, computed only on the anchor's own shock-date subset — not a
generic, unconditional correlation. `peer_relative_strength` already
covers general rolling correlation between watchlist peers.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`
- **Output (`angle_data`, dict):** Shock cluster membership for the
  symbol. Note: `trade_plan_authoring.py::_build_risk_band` and
  `_build_contingency_rules` both read a real `cluster_members` list
  field from this angle's latest row, confirming that field name.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 1,
  "data": [
    {
      "cluster_members": ["MSFT", "GOOGL"],
      "co_shock_rate": 0.35,
      "shock_day_correlation": 0.58,
      "shock_day_correlation_ci": [0.31, 0.79]
    }
  ]
}
```

## Condensed glossary blurb (draft)

*Real, load-bearing angle — `cluster_members` directly shrinks this
system's real position-size cap (`max_cluster_exposure_pct`) and adds a
real contingency rule if populated. Shock-day-only correlation, not a
general one; distinct from `peer_relative_strength`'s continuous
version.* (~40 words)
