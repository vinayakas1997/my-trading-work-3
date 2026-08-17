---
name: itransformer-implementation
status: phase-1-done
purpose: the real record of implementing iTransformer's walk-forward backtest against the shared infrastructure.
---

# 09 — itransformer — Implementation Record

## Files touched

| File | New/Edited | What changed |
|---|---|---|
| `vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/compute.py` | Edited | `MIN_BARS` raised 90→100. Extracted `_fit_and_forecast()` (returns the trained model too) — **and fixed the exact gap the design doc identified**: the model already computes a forecast for all 5 channels internally, but the original code only ever extracted `close`, discarding `open`/`high`/`low`/`volume`. Now all 5 are reported, in both `compute()`'s single-shot output and the backtest. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/backtest.py` | New | `itransformer_step` (direction-match hit + weights save) + `run_itransformer_backtest`, same shape as DLinear's. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/naive_baseline.py` | New | RMSE/MAE-only naive baseline. |
| `vinu-initial-analysis/vinu_initial_analysis/angles/itransformer/spec.yaml` | Edited | Stale `outputs.description` still said "close-channel forecast" only — fixed to mention all 5 channels. (`time_formats` already at the decided 6.) |
| `vinu-initial-analysis/tests/test_itransformer_backtest.py` | New | 5 tests. |

## How it was implemented

Group A, structurally closest to DLinear: a fresh model (real multi-head
attention across 5 channel-tokens, not true cross-asset attention — see
the design doc's own caveat, unchanged and out of scope here) trained
from scratch at every walk-forward step, every step's weights saved via
the same `WeightsStore` pattern DLinear already established. Direction-
match hit (no confidence interval in this model's output).

**One decision worth naming**: my first draft of `naive_baseline.py`
included a `hit` field (comparing naive's trivial "flat" direction
against the actual direction) — inconsistent with the reasoning already
established for ARIMA/Chronos/exponential_smoothing's naive baselines
(a constant "no change" forecast has no real direction to be right or
wrong about; comparing it that way just measures how often the market
happened to not move). Caught before committing to it, not after — fixed
to RMSE/MAE only, matching every other naive baseline this session.

## Testing

5 new tests + the 5 pre-existing `test_itransformer.py` tests (all still
pass unchanged, confirming the refactor and the channel-forecast fix
didn't break `compute()`'s existing behavior). Covers: row count, all 5
channel forecasts present and finite, tag correctness, weights
saved/reloadable, and that the naive baseline has no `hit`/`weights_ref`
columns.

**Real-data validation (Phase 1: `1D`)**: 125 real AAPL daily bars → 25
rows in 4.43s. All 5 real channel forecasts present (previously would
have silently discarded 4 of them). Tags matched standalone `tag_row`.
Weights saved and reloadable. Storage round-trip and `query_slice`
verified exactly against a hand pandas `groupby`.

**Real finding**: naive clearly beat iTransformer on this real window —
RMSE 6.50 (naive) vs. 12.95 (iTransformer), directional accuracy only
36% (worse than a coin flip). A meaningfully larger gap than ARIMA/
Chronos/exponential_smoothing showed against naive on the same data —
plausibly consistent with the design doc's own honest caveat that this
is a channel-as-token workaround, not the paper's true cross-asset
mechanism, though a 25-step, one-symbol sample is far too small to
attribute the gap specifically to that. Recorded as-is.

**Full `vinu-initial-analysis` suite**: 265 passed (up from 260
pre-this-angle — the 5 new tests), 2 skipped, the same 11 pre-existing
`shock_clustering`/`shock_personality` failures, no new failures.

## Related files

- `02-real-scenario.md` — the real example.
- `../plan.md` — overall status table.
- `../../04-enhancement-of-each-angle/09-itransformer.md` — the decided design.
