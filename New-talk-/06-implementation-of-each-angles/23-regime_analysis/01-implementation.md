---
name: regime_analysis-implementation
status: phase-1-done
purpose: the real record of fixing regime_analysis's confirmed look-ahead leak and adding the two new outputs the design doc proposed.
---

# 23 — regime_analysis — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/compute.py` | Edited | **Real bug fix**: replaced the leaky full-sample `vol.quantile(0.7)` threshold with `news_price_causality/regime_features.py`'s already-validated rolling z-score (120-period trailing baseline, `high_vol` if `z > 1.0`). Bull/bear classification changed from single-period `pct_change()` to 20-period cumulative return, matching the same already-validated module. `MIN_OBSERVATIONS` = 141 (120+21, a real derived floor, not the N=100 convention). Extracted `_compute_regime_frame()` (point-in-time-safe regime classification) so `backtest.py` can reuse it. Added normalized `transition_prob`/`n_from_regime` to the existing transition rows. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/backtest.py` | New | `run_per_bar_regime_backtest()` (new Layer-1 per-bar tagged rows, day-of-week/week/month/quarter only) + `run_quarterly_regime_breakdown()` (new per-(symbol, quarter, regime) counts + pct_of_time_in_quarter). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/regime_analysis/spec.yaml` | Edited | `time_formats` widened to the standard 6 plus the existing `1W`/`1M` kept (union, same approach as `backtesting_44_metrics`). |
| `vinu-initial-analysis/tests/test_signal_contract.py` | Edited | `test_regime_analysis_output_carries_usage_tags` used 40 synthetic bars, now below `MIN_OBSERVATIONS=141` — raised to 160 bars so it still exercises the `regime_stats` path instead of `insufficient_data`. |
| `vinu-initial-analysis/tests/test_regime_analysis_backtest.py` | New | 8 tests. |

## How it was implemented

This is the one angle in this session with a **confirmed, cross-
referenced bug** rather than a judgment call or a missing feature: the
design doc names three independent pieces of evidence that the original
`vol.quantile(0.7)` threshold was a real look-ahead leak (computed over
the entire sample series, so an early bar's regime label could depend on
volatility that hadn't happened yet) — the leak's own math, a sibling
module's docstring naming the defect by name and building a workaround
specifically to avoid it, and `signal_contract.py`'s registry already
restricting `regime_feature`'s proven uses because of this exact issue.
The fix wasn't a new invention: `news_price_causality/regime_features.py`
already had a validated, point-in-time-safe formula (rolling z-score
against a 120-day trailing baseline), so this angle now consolidates
onto that exact same method instead of maintaining two divergent regime
definitions in the same codebase.

`_compute_regime_frame()` is the shared core: a point-in-time-safe
DataFrame (bar_ts, single-period `ret` for the stats aggregation,
`ret_20d`/`vol`/`vol_trailing_z` for classification, `regime`). `compute()`
still emits its original three output shapes (`regime_stats`,
`regime_transitions`, `transition`) — same external shape as before,
just internally correct now, plus the new `transition_prob`/`n_from_regime`
fields per the design's "never present a rate without n" rule.
`backtest.py`'s two new functions are genuinely new outputs (per the
design's own Layer 1/quarterly-breakdown proposal), not a fix to
anything — they didn't exist in any form before.

## Testing

11 tests total: 4 pre-existing `test_signal_contract.py` tests (1 fixed
for the new `MIN_OBSERVATIONS` floor, confirming `signal_contract.py`'s
`tag_row` usage-contract tagging still applies correctly to the corrected
`regime_stats` rows) + 8 new backtest.py tests covering: `classify_regime`'s
priority order (high_vol beats bull/bear when both conditions are true,
per the design's explicit rule) and its bull/bear/sideways thresholds,
`insufficient_data` below the real 141-observation floor, transition rows'
normalized probability bounds and arithmetic, per-bar rows' date-only
tagging (no session/subsession) and value ranges, and quarterly
breakdown percentages summing to 1.0 per quarter.

**Real-data validation (Phase 1: `1D`)**: full real AAPL 1D history (1025
real bars, 2022-01→2026, well above the 141-bar floor) → 21 `compute()`
rows (4 regime_stats + 1 regime_transitions + 16 transition pairs), 885
per-bar rows (2022-01→2026, minus the 140-bar warmup), 52
(quarter, regime) breakdown rows. Tags matched standalone `tag_row`.
Storage round-trip verified for all three outputs (compute's own rows,
the new per-bar rows under a `regime_analysis_per_bar` bucket, the new
quarterly breakdown under `regime_analysis_quarterly` — same distinct-
angle-name-suffix convention as `backtesting_44_metrics`/
`news_price_causality`). `transition_prob` summed to ~1.0 (rounding-only
deviation) for every `regime_from` group, confirming the normalization is
correct.

**Real finding — the leak fix's effect is directly visible and
verifiable**: grouping the real per-bar rows by regime and averaging
`vol_trailing_z`, `high_vol` bars average **z≈2.00** (correctly well
above the 1.0 threshold that defines the regime), while `bear`/`bull`/
`sideways` average -0.43/-0.71/-0.51 (correctly below it) — real,
internally consistent confirmation the corrected classification logic
does what it's supposed to, not just that it runs without error. On this
real AAPL history: bull dominated (46.4% of classified bars, Sharpe
3.20), bear was the worst regime (23.3% of bars, Sharpe -1.86), high_vol
was mildly negative (21.0% of bars, Sharpe -0.09) — a real, honestly
measured regime profile, not assumed in advance.

**Full `vinu-initial-analysis` suite**: run after this angle; see
`../plan.md`'s status table entry for the pass count.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/23-regime_analysis.md` — the decided design, including the full leak-bug evidence trail.
