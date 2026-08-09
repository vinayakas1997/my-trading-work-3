---
name: shock_clustering-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the shock-conditional redesign actually works, with a genuinely differentiated real result between two peers.
---

# 24 — shock_clustering — Real Scenario

Real AAPL as anchor, real TSLA + JNJ as peers, full real 2022-2026 1D
history (same cached dataset as `peer_relative_strength`/`regime_analysis`).

## The calls

```python
from vinu_initial_analysis.angles.shock_clustering.compute import compute
from vinu_initial_analysis.angles.shock_clustering.backtest import run_shock_date_backtest

df = compute("AAPL", bars=bars, price_client=client, from_ts=..., to_ts=...)  # 0.34s
shock_rows = run_shock_date_backtest("AAPL", bars)  # 107 rows
```

## Real output — the shock-conditional co-movement summary

```json
{
  "symbol": "AAPL", "status": "ok", "n_shock_dates": 107,
  "cluster_members": [
    {
      "symbol": "TSLA", "n_anchor_shock_dates": 107, "n_co_shocked": 37,
      "co_shock_rate": 0.3458, "n_shock_day_pairs": 107,
      "shock_day_correlation": 0.5949, "correlation_ci": [0.4079, 0.7418]
    },
    {
      "symbol": "JNJ", "n_anchor_shock_dates": 107, "n_co_shocked": 33,
      "co_shock_rate": 0.3084, "n_shock_day_pairs": 107,
      "shock_day_correlation": 0.1672, "correlation_ci": [-0.0492, 0.3596]
    }
  ]
}
```

## Real output — one shock-date row (new, Layer 1)

```json
{
  "symbol": "AAPL", "bar_ts": 1645660800, "date": "2022-02-24",
  "trigger": "gap", "z": -2.96,
  "day_of_week": "thursday", "week_of_month": 4, "month": 2, "quarter": 1
}
```

Of 107 real detected shocks: 54 gap-triggered, 53 range-triggered.

## Storage + query round-trip, for real

```python
storage.write("AAPL", "shock_clustering", df, granularity="1D", tier="tier2")
storage.write("AAPL", "shock_clustering_shock_dates", shock_rows, granularity="1D", tier="tier2")
# both read back with exact row-count matches

query_slice(back_shock_dates, ["trigger"], {"avg_abs_z": ("z", lambda s: s.abs().mean())})
#  trigger   n  avg_abs_z
#      gap  54   2.619836
#    range  53   2.762585
```

## The real number: a genuinely differentiated shock-conditional signal

| Peer | Co-shock rate | Shock-day correlation | 95% CI |
|---|---|---|---|
| TSLA | 34.6% | **0.595** | **[0.408, 0.742]** — excludes zero |
| JNJ | 30.8% | 0.167 | [-0.049, 0.360] — crosses zero |

TSLA (another high-beta tech/growth name) shows a real, statistically
distinguishable-from-zero shock-day co-movement with AAPL. JNJ (a
defensive healthcare name) co-shocks at a similar raw *rate* but its
correlation is not distinguishable from noise — exactly the kind of
differentiated, honest answer "which symbols shock together" is supposed
to produce, and exactly what the old code's unconditional 63-day
correlation structurally could not have measured (it never looked at
shock dates at all, despite the angle's name and old `spec.yaml` both
claiming it did).

## A real bug found and fixed during this validation

The CI values above are **corrected** — the original `pearson_with_ci`
implementation returned `[-1.0, 1.0]` for both peers regardless of the
real underlying correlation, a `scipy.stats.bootstrap` pairing bug (see
`known-issues.md` #1, `01-implementation.md` for the full diagnosis).
Fixed before this document was written, so the numbers above are the
real, post-fix values throughout.

## Related files

- `01-implementation.md` — how this was built and tested, including both
  confirmed-bug fixes and the `pearson_with_ci` bootstrap-CI bug found
  along the way.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
