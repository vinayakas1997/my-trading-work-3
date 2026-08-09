---
name: peer_relative_strength-real-scenario
status: phase-1-done
purpose: one concrete, real example proving peer_relative_strength's backtest and forward-return validation actually work, and the real measured (null) predictive-value finding.
---

# 21 — peer_relative_strength — Real Scenario

Real AAPL as the symbol, real TSLA + JNJ as peers — the only 3 symbols
with cached price data in this project. Full real 1D history, 1025 real
trading days (2022-01 to 2026).

## The calls

```python
from vinu_initial_analysis.angles.peer_relative_strength.backtest import (
    run_relative_strength_backtest, run_forward_return_validation,
)

df = run_relative_strength_backtest("AAPL", bars, price_client=client)   # 394 rows, 0.04s
fwd = run_forward_return_validation("AAPL", bars, price_client=client)  # 32 rows, 0.22s
```

## Real output — one relative-strength row

```json
{
  "symbol": "AAPL", "date": "2022-04-04", "bar_ts": 1649030400,
  "peer_symbol": "JNJ", "correlation": 0.1124, "relative_return_20d": -0.0817,
  "day_of_week": "monday", "week_of_month": 1, "month": 4, "quarter": 2
}
```

No `session`/`subsession` fields — dropped per the design's "no intraday
dimension to tag" decision.

## Real output — one forward-return-validation bucket (corrected CIs)

```json
{
  "symbol": "AAPL", "peer_symbol": "JNJ", "quarter_key": "2022-Q3", "n_rows": 12,
  "forward_5d_corr": 0.3799, "forward_5d_p_value": 0.223,
  "forward_5d_ci_lower": -0.265, "forward_5d_ci_upper": 0.8217,
  "forward_10d_corr": 0.4677, "forward_10d_p_value": 0.125,
  "forward_10d_ci_lower": -0.1674, "forward_10d_ci_upper": 0.8913,
  "forward_20d_corr": 0.2103, "forward_20d_p_value": 0.512,
  "forward_20d_ci_lower": -0.3215, "forward_20d_ci_upper": 0.6262
}
```

(Corrected after `known-issues.md` #1's `pearson_with_ci` bootstrap-CI
fix, found later during angle 24 — the `corr`/`p_value` values above were
always correct; only the `ci_lower`/`ci_upper` fields changed, from a
degenerate `[-1, 1]` to real, bounded bands.)

## Storage + query round-trip, for real

```python
storage.write("AAPL", "peer_relative_strength", df, granularity="1D", tier="tier2")
storage.write("AAPL", "peer_relative_strength_forward_validation", fwd, granularity="1D", tier="tier2")
# both read back with exact row-count matches

query_slice(back, ["peer_symbol"], {"avg_corr": ("correlation", "mean")})
#  peer_symbol    n  avg_corr
#          JNJ  197  0.128082
#         TSLA  197  0.414102
```

Matched a hand-computed pandas `groupby` exactly.

## The real number: forward-return predictive value, on this real sample (corrected)

A real, subtle property of this angle's own design, confirmed while
correcting the CI bug: `relative_return_20d` is computed against the
**whole peer basket average** (`compute.py`'s `basket_return`), not
per-peer — so for a given quarter, the JNJ-row and TSLA-row forward-
return correlations are numerically identical (same `x`, same `y`).
The truly independent tests are 16 quarters × 3 horizons = **48**, not
96 (32 peer×quarter rows × 3 horizons) — the peer grouping doesn't
differentiate this particular correlation, only the raw `correlation`
column (63-day rolling, genuinely per-peer) does.

Of those 48 independent (quarter, horizon) tests, **7 crossed p<0.05**
— more than the ~2.4 expected by chance alone at α=0.05, but the sign
flips across quarters (some positive, some negative) and mostly clusters
at the 20-day horizon (5 of 7), not a stable, tradeable directional
signal. Recorded as an honest, nuanced finding — not the flatter "no
significant predictability" claim this document originally made before
the CI bug was found and fixed: there's a weak, inconsistent-direction
hint of forward-return dependence at longer horizons, not nothing, but
not a clean signal either.

| Peer | Avg raw 63-day correlation |
|---|---|
| JNJ | 0.128 |
| TSLA | 0.414 |

Same convention as every other angle's real finding this session — a
larger peer basket, longer real history, and (per the design observation
above) a per-peer-conditioned relative-return variant would all be
needed before drawing a stronger conclusion either way.

## Related files

- `01-implementation.md` — how this was built and tested, including the
  second real corrupt-parquet-file instance (JNJ).
- `../../05-storage-enhancement-levels/angle-validation-checklist.md` — the checklist this satisfies.
