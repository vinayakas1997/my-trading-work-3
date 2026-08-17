---
name: lstm-implementation
status: phase-1-done
purpose: the real record of implementing LSTM's walk-forward backtest against the shared infrastructure.
---

# 14 — lstm — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/lstm/compute.py` | Edited | `MIN_BARS` raised 80→100. Extracted `_fit_and_forecast()` (returns the trained model too) — `compute()`'s external behavior unchanged. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lstm/backtest.py` | New | `lstm_step` (direction hit + RMSE/MAE fields + weights save) + `run_lstm_backtest`, same shape as lpatchtst's. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lstm/naive_baseline.py` | New | RMSE/MAE-only naive baseline, same convention as every other point-forecast angle. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/lstm/spec.yaml` | Not touched | Already at the decided 6 `time_formats` from the earlier batch-fix pass; purpose text didn't repeat the miscited ~51% figure the design doc flagged, so no correction was needed here (unlike lpatchtst's spec.yaml). |
| `vinu-initial-analysis/tests/test_lstm_backtest.py` | New | 5 tests, same shape as lpatchtst's/dlinear's. |

## How it was implemented

Group A, structurally identical to DLinear/lpatchtst: a fresh single-layer
LSTM (`hidden_size=16`, no patching — per the design doc, a genuinely
small recurrent net, not a token gesture) trained from scratch at every
walk-forward step, every step's weights saved via `WeightsStore`.
Direction-match hit (native 1-step point forecast, no confidence
interval), plus `close_sq_error`/`close_abs_error` fields on the angle's
own step, same as lpatchtst/itransformer.

No architectural surprises versus lpatchtst's already-proven pattern —
`_fit_and_forecast()` returns `(fields, model)` exactly the same shape,
`backtest.py`/`naive_baseline.py` are near-identical to lpatchtst's minus
the patch branch.

## Testing

5 new tests + 4 pre-existing (`test_lstm.py`, all still pass unchanged —
its `n=30`/`n=200` fixtures straddle both the old `MIN_BARS=80` and the
new `MIN_BARS=100`, so the raise didn't need a test fix, unlike
exponential_smoothing/kalman_filters earlier in this session). Covers:
row count, tag correctness, hit/RMSE/MAE field consistency, weights
saved/reloadable, naive baseline's absent `hit`/`weights_ref` columns.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars
(Alpaca, same dataset shape as every other Phase-1 `1D` check this
session) → 25 rows in 3.56s. Tags matched standalone `tag_row`. Weights
saved and reloadable (`lstm.weight_ih_l0`, `lstm.weight_hh_l0`,
`head.weight`, and friends — a real trained LSTM's state). Storage
round-trip verified: the 26 real result columns matched exactly;
`AngleStorage.write()`'s own added metadata columns (`run_id`,
`angle_name`, timestamps) were the only diff, confirmed by an explicit
column-set diff, not just eyeballing `.equals()`. `query_slice`'s grouped
hit-rate-by-day-of-week matched a hand pandas `groupby` exactly.

**Real finding**: 44% directional accuracy on this real (small, 25-step)
sample — below the corrected paper benchmark of 55.4% (arXiv:2603.01820).
Naive beat this angle on both RMSE (3.80 vs. 4.25) and MAE (2.61 vs.
3.33). Recorded honestly, same as every prior angle's real finding this
session — the paper's own benchmark universe/date range differs from this
project's, a caveat the design doc already flags, so this isn't treated as
a refutation, just an honest report of what this specific small real check
measured.

**A real, pre-existing data-corruption issue found (not part of this
angle's code)**: `data/stock-price/prices/1m/AAPL/live/2026_20260205.parquet`
is truncated (8399 bytes, fails DuckDB's magic-bytes check) — it blocks
`vinu_stock.query.engine.fetch_candles()` entirely for AAPL, since
`parquet_globs()` globs every live file unconditionally before any
date-range filtering happens in pandas. Worked around for this
validation by loading all AAPL archive+live parquet files directly via
pandas, excluding the one corrupt file, then aggregating to `1D` via
`vinu_stock.query.aggregate.aggregate_bars()` — same real data, same
aggregation path the shared engine itself uses, just without going
through the one broken file. Not fixed here at the time (an ingest/
data-repair concern, out of scope for an angle's own backtest code) —
tracked in `known-issues.md`. **Since fixed in a dedicated pass**
(`known-issues.md` Resolved #3): atomic writes on the ingest side,
resilient per-file skipping on the read side, and the corrupt file itself
deleted after a full-cache audit (which also found a third instance on
TSLA, sharing the exact same date as this AAPL file). `fetch_candles`
now works normally for AAPL with no workaround needed.

**Full `vinu-initial-analysis` suite**: 288 passed (up from 283
pre-this-angle — the 5 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../known-issues.md` — the corrupt-live-parquet-file tracking entry (Resolved #3).
- `../../04-enhancement-of-each-angle/14-lstm.md` — the decided design, including the source-citation correction.
