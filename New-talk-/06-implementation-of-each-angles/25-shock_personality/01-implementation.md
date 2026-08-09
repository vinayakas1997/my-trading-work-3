---
name: shock_personality-implementation
status: phase-1-done
purpose: the real record of fixing shock_personality's three confirmed bugs and surfacing previously-discarded computation as real, queryable output.
---

# 25 — shock_personality — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/compute.py` | Rewritten | **Bug #1 fix**: gap trigger now uses `.rolling(21)` mean/std (was a full-sample constant — an independently-reimplemented duplicate of `shock_clustering`'s own fixed bug, not shared code). **Bug #2 fix**: `_compute_drift_metrics` (renamed from `_compute_drift_persistence`) now also aggregates and returns `drift_mean_autocorr` — the per-shock autocorrelation values were already being computed, only the "is there at least one non-NaN value" check survived before. **Bug #3 fix**: `has_news`/`nearest_news_days` (already computed by `_cross_reference_news`) now used to split `gap_fill_rate` and `drift_persistence_days` into `_news`/`_no_news` variants, not just discarded after computation. `MIN_OBSERVATIONS=21` (the real rolling-window floor). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/backtest.py` | New | `run_shock_backtest()` — new Layer-1 per-shock tagged rows, surfacing `has_news`/`nearest_news_days` per row (Bug #3's other half — the design doc wants both the per-row values and the aggregate split). Gap rows always get date-only tags; vol-spike rows get full tagging (session/subsession) only on intraday timeframes, per the design's explicit per-trigger-type tagging rule. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/_helpers.py` | Edited | Added `mean_with_ci()` — the same mean/n/CI shape `pnl_attribution`'s own `_rate_with_ci` already used, generalized here since this angle alone needs the identical pattern 8+ times (gap fill, drift persistence, mean autocorrelation, each split by news presence). Adds a `note: "thin sample, n<10"` flag for `2 <= n < 10`, per this angle's own decided "thin-sample caution" rule — a feature `pnl_attribution`'s version didn't need. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/shock_personality/spec.yaml` | Edited | Purpose text updated to describe the now-real (not discarded) `drift_mean_autocorr` and news-split fields. `time_formats` widened to the standard 6 (the design doc's own §7 rationale prose argues gap detection should stay 1D-only, but its "Decided parameters" table explicitly marks both triggers "updated: widened to the standard 6" — followed the table, the authoritative decided-values section, and flagged this internal inconsistency in the design doc rather than silently picking one). |
| `vinu-initial-analysis/tests/test_shock_personality.py` | Rewritten | 15 tests, including a fixed `bar_ts` column in the synthetic fixture — resolves the remaining 8 of the 11 pre-existing `KeyError: 'bar_ts'` failures this session inherited (the other 3 were `shock_clustering`'s, fixed in angle 24). |

## A documentation inconsistency found, not a code bug

The design doc's §7 rationale is headed "Why gap detection stays 1D-only
while vol-spike detection widens," but the SS3 "Decided parameters" table
explicitly marks the gap-shock timeframe scope row "**updated**: widened
to the standard 6" — the opposite of what the rationale prose argues.
Read as a genuine leftover from an earlier draft (plausibly from the
project-wide later pass that widened every angle's timeframes to 6,
which apparently updated this table row without syncing the prose
underneath it). Followed the table, since it's explicitly marked as the
final decided value and every other angle's design doc treats its
"Decided parameters" table as authoritative over any earlier-drafted
rationale text.

## How it was implemented

Group B, with **three confirmed bugs**, the most of any angle checked
this session — one leak (Bug #1, same class already fixed in
`regime_analysis`/`shock_clustering`, but genuinely a separate
implementation here per the design doc's own note: "independently
reimplemented here, not shared code") and two "computed then discarded"
bugs (Bug #2/#3), the same category previously found in
`drawdown_deep_dive`'s dead `lookback_hours` field. Both discard bugs
were fixed the same way: use the already-computed values instead of
either deleting the computation or leaving it silently wasted.

`_compute_drift_metrics` walks each shock's post-event return window
once and produces both drift views (sign-streak `drift_persistence_days`
and the new continuous `drift_mean_autocorr`) from that single pass,
rather than computing autocorrelations twice. The news split
(`_news_split`) is a simple has_news partition reused for both
`gap_fill_rate` and the drift metrics, computed by calling the existing
(parameterized-by-shock-list) functions again on each subset — no
duplicated aggregation logic, since `_compute_gap_fill_rate`/
`_compute_drift_metrics` already accepted an arbitrary shock list.

## Testing

15 tests: shock detection (gap/vol-spike), news cross-referencing,
gap-fill-rate computation, real GARCH vol-persistence (reuses the same
`vinu_tools.compute.risk.volatility.garch_volatility` the `garch` angle
itself uses — including, at the time this angle was built, that angle's
own known `omega` estimator bug, `known-issues.md` Resolved #2, inherited
here unchanged at the time since fixing it was out of scope for this
angle too; since fixed in a dedicated pass, see below), the new
`_compute_drift_metrics`'s dual-view output shape,
`insufficient_data` below the real 21-bar floor, the full `compute()`
output's news-split/autocorr fields all present, and the new backtest
rows' per-trigger-type tagging rule (gap rows never get `session`).

**Real-data validation (Phase 1: `1D`)**: full real AAPL 1D history
(1025 real bars) + the same 156 real cached AAPL news articles used for
`news_price_causality`'s validation (Jan 2023 only — the project's real
news cache's actual coverage window, same limitation already documented
there). 107 real shocks detected (54 gap, 53 vol-spike) in 0.39s. Only 1
of 107 real shocks falls within the news-cache's narrow real coverage
window, so the news-split metrics correctly report `insufficient_sample`
for the `_news` variant (n=1) while `_no_news` carries the full real
sample — an honest reflection of this project's real news-data coverage
gap, not a bug in the split logic itself (verified separately with
synthetic data covering both branches in the unit tests). Storage
round-trip verified for both outputs (zero mismatches). Tags matched
standalone `tag_row`. `query_slice`'s grouped average |z-score| by
trigger type matched shock_clustering's own real numbers exactly (gap:
2.62, vol_spike/range: 2.76) — expected, since both angles detect shocks
on the identical real AAPL series with the identical rolling-window
formula, now that both leaks are fixed.

**Real finding — real GARCH volatility persistence**: alpha=0.100,
beta=0.855, persistence=0.955 (α+β close to 1, real, plausible high
volatility clustering for AAPL) — the same `garch_volatility` function
the `garch` angle (08) itself validated, reused here unchanged. **Updated
after `known-issues.md`'s Resolved #2 GARCH `omega` fix** (re-run on the
same full real AAPL 1D history): alpha=0.072, beta=0.901,
persistence=0.973 — directionally the same finding (persistence still
close to 1, still high real volatility clustering), with `omega` itself
now landing within ~1.05x of the variance-targeting sanity identity
(previously ~1,820x off, though this didn't change the persistence
narrative much since `alpha`/`beta` were already reasonably bounded even
under the old buggy optimizer — the bug's real damage was concentrated in
`omega`'s own magnitude, which this angle's `vol_persistence` field
stores but doesn't otherwise use downstream).
**Real finding — post-shock drift is short and mean-reverting on this
sample**: mean sign-streak 1.01 days (shocks don't sustain directional
follow-through for more than ~1 day on average), mean autocorrelation
**-0.051, CI [-0.064, -0.038]** — small but real and excludes zero,
consistent with mild post-shock mean-reversion rather than momentum on
this real AAPL sample.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count (this closes out
all 11 originally-known pre-existing `bar_ts` failures — 3 from
`shock_clustering`, 8 from this angle).

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../known-issues.md` — the now-fixed GARCH `omega` estimator bug (Resolved #2), which affected this angle's `vol_persistence` field until the dedicated fix pass.
- `../24-shock_clustering/01-implementation.md` — the sibling angle with the same independently-reimplemented gap-detection leak.
- `../../04-enhancement-of-each-angle/25-shock_personality.md` — the decided design, including the timeframe-scope table/prose inconsistency.
