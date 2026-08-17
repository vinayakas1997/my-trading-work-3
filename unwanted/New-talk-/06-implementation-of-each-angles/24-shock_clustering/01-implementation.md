---
name: shock_clustering-implementation
status: phase-1-done
purpose: the real record of fixing shock_clustering's two confirmed bugs and rebuilding it as a genuinely shock-conditional co-movement signal — plus the real pearson_with_ci CI bug found and fixed along the way.
---

# 24 — shock_clustering — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/compute.py` | Rewritten | **Bug #1 fix**: gap trigger now uses `.rolling(21)` mean/std (was a full-sample constant, same leak class as `regime_analysis`'s fix). **Bug #2 fix**: dropped the unconditional `dynamic_covariance`-based correlation entirely (never actually conditioned on shock dates despite the angle's name/spec claiming it did); replaced with genuinely shock-conditional `co_shock_rate` (±1-day peer co-occurrence) and `shock_day_correlation` (Pearson + bootstrapped CI, computed only on the anchor's shock-date subset, via the shared `pearson_with_ci`). `MIN_OBSERVATIONS=100`, `MIN_SHOCK_DATES=5` thin-sample floor (`insufficient_shock_sample` status). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/backtest.py` | New | `run_shock_date_backtest()` — new Layer-1 per-shock-date tagged rows (day-of-week/week/month/quarter, no session). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_clustering/spec.yaml` | Edited | Purpose text corrected (no longer claims "dynamic covariance sampled at shock dates" — the confirmed-false claim Bug #2 was about). `time_formats` widened to the standard 6. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py` | Edited | **Real bug found and fixed**: `pearson_with_ci`'s bootstrap CI was always the degenerate `[-1, 1]` regardless of real correlation strength or sample size (a `scipy.stats.bootstrap` un-paired-resampling mistake). Fixed with `paired=True`/`vectorized=False` + a NaN guard for small-sample degenerate resamples. Full diagnosis in `known-issues.md` #1 (Resolved). |
| `vinu-initial-analysis/tests/test_shock_clustering.py` | Rewritten | 10 tests, including a fixed `bar_ts` column in the synthetic fixture — this also resolves the 3 pre-existing `KeyError: 'bar_ts'` failures this angle had going into this session (the fixture never carried `bar_ts`, only a `DatetimeIndex`). |

## How it was implemented

Group B, with **two confirmed, cross-referenced bugs**, not judgment
calls — the design doc verified both directly against the real code
(Bug #1: the gap trigger's full-sample constant, identical defect class
to `regime_analysis`'s just-fixed leak; Bug #2: read
`vinu_tools/compute/risk/covariance.py`'s `dynamic_covariance()`
directly and confirmed it takes an unconditional trailing-63-day window
with zero awareness of which days were shocks — the `shock_dates` list
was computed but only ever used for reporting, never to condition the
correlation, despite the angle's name and `spec.yaml` both claiming
shock-conditional analysis).

The rewrite: `_detect_shocks()` returns real per-shock records (bar_ts,
date, trigger type, z-score) instead of a bare date-string list, so both
`compute()`'s summary and `backtest.py`'s new per-date rows can use the
same detection pass. `_co_shock_and_correlation()` is the actual new
signal — for each peer, independently detects that peer's *own* shocks
(fetched with full OHLC, not just close, specifically so its own
gap/range triggers can run), checks how many land within
`CO_SHOCK_WINDOW_DAYS` of an anchor shock date, and computes Pearson
correlation + bootstrap CI restricted to the anchor's shock-date return
subset. The old generic correlation was dropped entirely, not kept
alongside — per the design doc, keeping it would duplicate
`peer_relative_strength` (angle 21) with a strictly weaker,
non-shock-conditional method.

## A real bug found in shared infrastructure, not this angle's own code

While validating the new `shock_day_correlation` against real AAPL/TSLA
data, the bootstrapped CI came back `[-1.0, 1.0]` — obviously wrong for
n=107 real shock-day pairs. Traced to `pearson_with_ci()` (added for
angle 21, `peer_relative_strength`, generalized from
`news_price_causality/correlation.py`'s own pre-existing bootstrap
pattern): passing `list(zip(x, y))` as a single un-paired sample let
`scipy.stats.bootstrap` auto-vectorize the statistic function in a way
that decorrelated `x` from `y` per resample. Confirmed directly with a
synthetic series with a real, known 0.6 correlation — still produced
`[-1.0, 1.0]`. Fixed using `scipy.stats.bootstrap`'s built-in
`paired=True` resampling mode (confirmed via the same synthetic A/B
test: `paired=True` gives `[0.42, 0.65]` around the real 0.53 measured
value), plus a NaN guard for the separate small-sample-size failure mode
(a degenerate constant resample making `pearsonr` return NaN).

This bug predates this angle — it was shipped with angle 21's
`peer_relative_strength` implementation, whose own real-scenario doc
originally (incorrectly) attributed the wide CIs to small sample size.
**Retroactively corrected** in `21-peer_relative_strength/01-implementation.md`
and `02-real-scenario.md` with the real, re-run numbers. Full bug
write-up, including the still-unfixed sibling bug in
`news_price_causality/correlation.py`'s own original bootstrap block
(not currently exposed in that angle's stored output, so lower priority,
tracked separately), in `known-issues.md`.

## Testing

10 tests: shock detection on calm synthetic data (no false positives),
detection of deliberately injected large-gap shocks, the date-only view
matching the full-record view, `insufficient_data`/`insufficient_shock_sample`
status boundaries, empty `cluster_members` with no peer, and — with a
fake price client providing a peer that shares the anchor's injected
shock dates — a real, measurable positive `co_shock_rate`. Also 2 tests
for the new per-shock-date backtest rows (tagging, empty-below-floor).
Fixing the synthetic fixture's missing `bar_ts` column (the pre-existing
bug this angle's tests had) was necessary to write any of these, not an
optional side effect.

**Real-data validation (Phase 1: `1D`)**: real AAPL as anchor, real TSLA
+ JNJ as peers (full real 2022-2026 history). 107 real shock dates
detected (54 gap-triggered, 53 range-triggered — a real, roughly even
split) in 0.34s. Storage round-trip verified for both outputs
(`shock_clustering` compute summary + `shock_clustering_shock_dates`
per-date rows, zero mismatches). Tags matched standalone `tag_row`.
`query_slice`'s grouped average |z| by trigger type matched a hand
aggregation (gap: 2.62, range: 2.76).

**Real finding — a genuine, well-differentiated shock-conditional
signal, not noise**: TSLA co-shocks with AAPL 34.6% of the time, with a
shock-day correlation of **0.595, CI [0.408, 0.742]** — clearly excludes
zero, a real signal. JNJ co-shocks 30.8% of the time but its
shock-day correlation is only 0.167, CI **[-0.049, 0.360]** — crosses
zero, not statistically distinguishable from no relationship. This is
exactly the kind of differentiated, real result the design doc's
redesign was meant to produce (a genuine "do these symbols shock
together" answer) that the old generic-correlation code structurally
could not have produced.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count (also resolves 3 of
the 11 previously-known pre-existing failures — `shock_clustering`'s own
`bar_ts` fixture bug).

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../known-issues.md` — the `pearson_with_ci` bug (Resolved #1) and its sibling in `news_price_causality/correlation.py`, since fixed the same way (Resolved #5).
- `../21-peer_relative_strength/01-implementation.md` — retroactively corrected for this same CI bug.
- `../../04-enhancement-of-each-angle/24-shock_clustering.md` — the decided design, including both confirmed-bug write-ups.
