# peer_relative_strength — Peer Relative Strength

**Cluster:** F — Cross-asset & causality

## Purpose (verbatim from `angles.yaml`)

Measures how a symbol performs relative to its watchlist peer basket
over time using rolling correlation and relative (excess) returns.
Stands apart from `shock_clustering` (which only answers "which symbols
shock together on shock dates") by computing peer co-movement and
relative strength as a continuous, windowed signal across the full
requested range.

## Real fields

- **Time formats:** 1min, 5min, 15min, 1H, 4H, 1D
- **Inputs:** `symbol: str`, `from_ts: int | None`, `to_ts: int | None`,
  `price_client: price_client | None`
- **Output (`angle_data`, dict):** Rolling peer correlation and
  excess-return rows per sampled bar: `date`, `peer_symbol`,
  `correlation` (63-day rolling), `relative_return_20d`.

## FAKE example result — for prompt-design/testing only, NOT a real computed value

> Synthetic, illustrative only. Never treat this as an actual AAPL (or
> any symbol) signal.

```json
{
  "row_count": 3,
  "data": [
    {"date": "2026-09-19", "peer_symbol": "MSFT", "correlation": 0.71, "relative_return_20d": 0.023},
    {"date": "2026-09-19", "peer_symbol": "GOOGL", "correlation": 0.58, "relative_return_20d": -0.011},
    {"date": "2026-09-19", "peer_symbol": "NVDA", "correlation": 0.44, "relative_return_20d": 0.061}
  ]
}
```

## Condensed glossary blurb (draft)

*Continuous, ongoing co-movement/relative-strength vs. this symbol's
real peer basket — not the same as `shock_clustering`, which only looks
at shock days specifically. Positive `relative_return_20d` means
outperforming that peer over the last 20 days.* (~40 words)
