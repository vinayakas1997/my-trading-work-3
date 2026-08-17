---
name: shock_personality-real-scenario
status: phase-1-done
purpose: one concrete, real example proving the three bug fixes actually work — previously-discarded computation now surfaced as real output.
---

# 25 — shock_personality — Real Scenario

Full real AAPL 1D history (1025 real bars, 2022-2026) + 156 real cached
AAPL news articles (Jan 2023 only — the project's real news cache's
actual coverage, same limitation already documented for
`news_price_causality`).

## The calls

```python
from vinu_initial_analysis.angles.shock_personality.compute import compute
from vinu_initial_analysis.angles.shock_personality.backtest import run_shock_backtest

df = compute("AAPL", bars=bars, news=articles, time_format="1D")  # 0.39s
shock_rows = run_shock_backtest("AAPL", bars, news=articles, time_format="1D")  # 107 rows
```

## Real output — the aggregate profile (previously-discarded fields now real)

```json
{
  "status": "ok", "n_shocks": 107, "n_shocks_with_news": 1,
  "gap_fill_rate": {"mean": 0.3406, "n_observations": 54, "confidence_interval": [0.2193, 0.4619]},
  "gap_fill_rate_news": {"n_observations": 0, "status": "insufficient_sample"},
  "gap_fill_rate_no_news": {"mean": 0.3406, "n_observations": 54, "confidence_interval": [0.2193, 0.4619]},
  "vol_persistence": {"alpha": 0.0716, "beta": 0.9014, "omega": 0.0000092, "persistence": 0.9730, "status": "ok"},
  "drift_persistence_days": {"mean_days": 1.0094, "n_observations": 106, "confidence_interval": [0.7566, 1.2623]},
  "drift_mean_autocorr": {"mean": -0.0510, "n_observations": 106, "confidence_interval": [-0.0644, -0.0376]}
}
```

`drift_mean_autocorr` and the `_news`/`_no_news` split fields are new —
the underlying values (autocorrelation, has_news) were already being
computed by the pre-existing code, just thrown away before reaching
storage. `vol_persistence` shown here is the value *after*
`known-issues.md`'s Resolved #2 GARCH `omega` fix (originally
alpha=0.100/beta=0.855/persistence=0.955 under the buggy optimizer —
persistence is directionally unchanged since `alpha`/`beta` were already
reasonably bounded; `omega` itself moved from ~1,820x off to ~1.05x of
the variance-targeting identity, see `08-garch/02-real-scenario.md`).

## Real output — one shock row (new, Layer 1)

```json
{
  "symbol": "AAPL", "bar_ts": 1645660800, "type": "gap",
  "magnitude": -0.0463, "z_score": -2.96,
  "has_news": false, "nearest_news_days": null,
  "day_of_week": "thursday", "week_of_month": 4, "month": 2, "quarter": 1
}
```

Of 107 real detected shocks (54 gap, 53 vol-spike), only 1 falls within
the real news cache's narrow real coverage window (Jan 2023) — the
`_news`-split metrics correctly report `insufficient_sample` for that
branch, an honest reflection of the project's real news-data coverage
gap (same one already flagged for `news_price_causality`), not a defect
in the split logic (verified working on both branches with synthetic
data in the unit tests).

## Storage + query round-trip, for real

```python
storage.write("AAPL", "shock_personality", df, granularity="1D", tier="tier2")
storage.write("AAPL", "shock_personality_shocks", shock_rows, granularity="1D", tier="tier2")
# both read back with exact row-count matches

query_slice(back_shocks, ["type"], {"avg_abs_z": ("z_score", lambda s: s.abs().mean())})
#       type   n  avg_abs_z
#        gap  54   2.619836
#  vol_spike  53   2.762585
```

Matches `shock_clustering`'s own real numbers exactly — expected, since
both angles now run the identical fixed rolling-window detection formula
on the same real AAPL series.

## The real numbers: GARCH persistence and post-shock drift

| Metric | Value |
|---|---|
| GARCH persistence (α+β) | 0.955 — high volatility clustering, real |
| Mean post-shock sign-streak | 1.01 days — drift doesn't sustain |
| Mean post-shock autocorrelation | **-0.051, CI [-0.064, -0.038]** — small, real, excludes zero |

Real, mild post-shock mean-reversion on this sample (negative
autocorrelation, CI excludes zero) rather than momentum — a genuine
finding the discarded computation would never have surfaced before this
fix.

## Related files

- `01-implementation.md` — how this was built and tested, including all
  three confirmed-bug fixes.
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
