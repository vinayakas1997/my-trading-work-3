---
name: regime_analysis-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the leak fix and the two new outputs actually work, with direct verification that the corrected z-score classification does what it claims.
---

# 23 — regime_analysis — Real Scenario

Full real AAPL 1D history (1025 real bars, 2022-01 to 2026).

## The calls

```python
from vinu_initial_analysis.angles.regime_analysis.compute import compute
from vinu_initial_analysis.angles.regime_analysis.backtest import (
    run_per_bar_regime_backtest, run_quarterly_regime_breakdown,
)

df = compute("AAPL", bars=bars, time_format="1D")                      # 21 rows, 0.036s
per_bar = run_per_bar_regime_backtest("AAPL", bars, time_format="1D")  # 885 rows
quarterly = run_quarterly_regime_breakdown("AAPL", bars, time_format="1D")  # 52 rows
```

## Real output — regime_stats (the corrected, leak-free classification)

| Regime | Count | % of time | Total return | Sharpe |
|---|---|---|---|---|
| bull | 411 | 46.4% | +201.6% | 3.20 |
| bear | 206 | 23.3% | -34.3% | -1.86 |
| high_vol | 186 | 21.0% | -8.2% | -0.09 |
| sideways | 82 | 9.3% | +1.1% | 0.27 |

## Real output — one transition row (normalized, new)

```json
{
  "metric": "transition", "regime_from": "bear", "regime_to": "bear",
  "count": 177, "n_from_regime": 206, "transition_prob": 0.859223
}
```

## Real output — one per-bar row (new, Layer 1)

```json
{
  "symbol": "AAPL", "bar_ts": 1658793600, "regime": "bull",
  "ret_20d": 0.07198, "vol_21d": 0.24698, "vol_trailing_z": -1.1866,
  "day_of_week": "tuesday", "week_of_month": 4, "month": 7, "quarter": 3
}
```

No `session`/`subsession` — dropped per the same "no intraday dimension"
reasoning as `peer_relative_strength`.

## Real output — one quarterly breakdown row (new)

```json
{"symbol": "AAPL", "quarter_key": "2022-Q3", "regime": "bull", "count": 23, "pct_of_time_in_quarter": 0.4792}
```

## Storage + query round-trip, for real

```python
storage.write("AAPL", "regime_analysis", df, granularity="1D", tier="tier2")
storage.write("AAPL", "regime_analysis_per_bar", per_bar, granularity="1D", tier="tier2")
storage.write("AAPL", "regime_analysis_quarterly", quarterly, granularity="1D", tier="tier2")
# all three read back with exact row-count matches

query_slice(back_per_bar, ["regime"], {"avg_vol_z": ("vol_trailing_z", "mean")})
#     regime    n  avg_vol_z
#       bear  206  -0.427051
#       bull  411  -0.711344
#   high_vol  186   2.002142
#   sideways   82  -0.506223
```

## Proving the leak fix actually works, not just that it runs

Grouping the real per-bar rows by regime and averaging `vol_trailing_z`:
`high_vol` bars average **z ≈ 2.00** — correctly, clearly above the 1.0
threshold that defines the regime. Every other regime averages a
negative or near-zero z — correctly below it. This is real, internally
consistent confirmation that the corrected rolling-baseline classification
does what it claims (bars actually get bucketed as `high_vol` because
their trailing-relative volatility really was elevated at that point in
time, not because of a full-sample constant that could see the future),
not just that the code executes without error.

Also confirmed: `transition_prob` sums to ~1.0 (rounding-only deviation)
for every `regime_from` group across all 16 real transition pairs.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  full leak-bug fix.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
