---
name: drawdown_deep_dive-implementation
status: phase-1-done
purpose: the real record of implementing drawdown_deep_dive's episode detection against the shared infrastructure — files touched, how it was built, how it was tested, and bugs found along the way.
---

# 06 — drawdown_deep_dive — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/drawdown.py` | Edited | Added `atr_pct_series()` (reuses the real `vinu_tools.compute.indicators.atr`), `_shape_checkpoints()`, and `detect_drawdown_episodes()` — the full peak→trough→recovery state machine with ATR-adaptive threshold. `get_drawdowns()`/`attribute_drawdown()` left untouched — `compute()` still calls them unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/backtest.py` | New | `run_drawdown_detection()` (one k) + `run_k_sweep()` (the design doc's own flagged-as-not-yet-run 1.5/2/2.5/3 sweep). |
| `vinu-initial-analysis/vinu_initial_analysis/angles/drawdown_deep_dive/spec.yaml` | Edited | `time_formats` widened from `[15min, 1H, 1D]` to the decided 6. |
| `vinu-initial-analysis/tests/test_drawdown_deep_dive_backtest.py` | New | 8 tests, see "Testing". |

## How it was implemented

This is **Group B**, and unlike every angle so far, not even a
fixed-cadence loop — `detect_drawdown_episodes` is a state machine over
the *entire* bars series that emits a variable number of episode rows,
data-dependent, not one row per candle or per step. It doesn't use
`run_walk_forward` at all.

The rolling-peak and recovery-trigger mechanism (a later candle's `high`
exceeding the *original* peak's `high`) reuses the same logic the
existing `get_drawdowns()` already had — extended with:
- **ATR-adaptive threshold**: `threshold_pct_used = -max(k * atr_pct_at_peak, 0.5)`,
  using the real `vinu_tools.compute.indicators.atr` indicator (a plain
  `SMA(true_range, 14)`, not Wilder's exact recursive smoothing — the
  decided design's emphasis was on the period and the no-lookahead
  property, both satisfied).
- **Full recovery lifecycle**: `recovery_ts`/`recovery_price`/
  `recovery_gain_pct`/`duration_to_recovery`/`recovery_speed`, all
  missing from the original code entirely.
- **Shape checkpoints**: first candle crossing 25/50/75% cumulative
  progress, computed as a second pass over `bars.iloc[peak_idx:trough_idx+1]`
  (formation) and `bars.iloc[trough_idx:recovery_idx+1]` (recovery) once
  an episode's boundaries are known — can't be computed incrementally
  since the trough keeps moving until the episode closes.
- **Formation/recovery news split**: plain timestamp-range filtering
  (`peak_ts ≤ ts ≤ trough_ts` / `trough_ts ≤ ts ≤ recovery_ts`), no
  attribution-weight formula — replaces `attribute_drawdown()`'s rejected
  `news_driven_pct` heuristic entirely for this new detection path
  (`attribute_drawdown` itself is untouched, still used by `compute()`'s
  existing single-worst-drawdown behavior).
- **Open (unrecovered) episodes** kept with `status: "open"`, every
  recovery field `null` — not dropped.

No weights store: nothing is trained.

## Testing

8 new tests in `tests/test_drawdown_deep_dive_backtest.py`, hand-built
synthetic OHLC scenarios (a 15-bar ATR warmup + sharp drop + recovery;
a never-recovers variant; a flat-price variant to check the min-threshold
floor). All 8 pass.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars →
**3 real episodes at k=2** (not zero — a genuine, non-trivial real
result), one shown in full in `02-real-scenario.md`. Storage round-trip:
written through the real `AngleStorage`, read back with an exact
row-count match. `query_slice` grouping by `day_of_week` matched a hand
pandas `groupby` exactly.

**The k-sweep, run for real** (closes the design doc's own "Open/
unresolved" item — the sweep "hasn't actually been run yet"):

| k | n_episodes | n_recovered | n_open | avg_drop_pct | avg_duration_to_trough | avg_duration_to_recovery |
|---|---|---|---|---|---|---|
| 1.5 | 6 | 5 | 1 | -7.7664 | 7.33 | 5.6 |
| 2.0 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |
| 2.5 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |
| 3.0 | 3 | 2 | 1 | -11.5797 | 12.00 | 12.5 |

Real finding: results are **stable for k ≥ 2.0** on this real 6-month
window (identical episode set, identical stats across 2.0/2.5/3.0) but
meaningfully more sensitive at `k=1.5` (doubles the episode count with a
much smaller average drop). This is exactly the kind of measured
robustness answer the design doc asked for — a single small real window,
so not the final word on stability, but a real one, not assumed.

## Bugs found and fixed

**Bug 1 — ATR-at-the-peak lookup can get permanently stuck during ATR's
own warmup window.** `atr_pct_at_peak` is looked up at the *peak*
candle's index (per the decided design), not the evaluation candle. If
the tracked peak happens to fall within the first `atr_period` (14)
bars — before `ATR(14)` has any real value there — `threshold_for(peak_idx)`
returns `None` forever, and since the rolling-peak tracker only ever
advances `peak_idx` to a *later*, *higher* candle, a peak stuck in the
warmup window with no later higher candle blocks detection completely,
even long after real ATR values exist elsewhere in the series. Found via
a hand-built synthetic test — the very first version detected **zero**
episodes despite a deliberate, obvious -10% single-candle drop; traced by
manually printing `peak_idx`/`atr_at_peak`/`threshold` per candle and
finding `atr_at_peak` was `None` for the entire run.
**Fix 1**: peak tracking now starts at the first index with a real ATR
value (`first_valid = next(idx for idx, a in enumerate(atr_pct) if a is not None)`),
not index 0 — the same `min_observations`-style discipline already
applied everywhere else in this project (ARIMA/DLinear/Chronos all
require real data before evaluation begins), just derived here from a
real bug instead of applied by convention up front.

**Full `vinu-initial-analysis` suite**: 247 passed (up from 239
pre-this-angle — the 8 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `00-plan.md` — the pre-implementation plan.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/06-drawdown_deep_dive.md` — the decided design.
