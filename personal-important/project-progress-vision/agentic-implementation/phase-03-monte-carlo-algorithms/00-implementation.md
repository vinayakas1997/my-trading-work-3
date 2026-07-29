# Phase 03: Monte Carlo Validation Algorithms

**Status:** COMPLETED
**Started:** 2026-07-24
**Depends on:** —
**Blocks:** Phase 04 (wire Monte Carlo gate into research loop)

## What It Delivers

Pure-math validation algorithms that make the Monte Carlo gate statistically rigorous. These have no storage dependency — they were built in parallel with Steps 1–2.

Three new functions added to `vinu-simulator/vinu_simulator/engine/validation.py`:

1. **`block_bootstrap_permutation()`** — Circular block bootstrap of trade P&Ls (preserves local dependence between consecutive trades, unlike full i.i.d. shuffling). More realistic null than the existing `monte_carlo_permutation()`.

2. **`price_path_resample()`** — Block-bootstrap of the daily return series, recomputing Sharpe on each resampled path. Tests robustness to price-path structure rather than just trade-execution order.

3. **`compute_validation_verdict()`** — Combines all validation sub-results (`monte_carlo`, `block_bootstrap`, `price_path`, `walk_forward`, `bootstrap`) into a single pass/fail verdict with documented reasons.

Also wired the new functions into `_run_validation_and_attribution()` in `service.py` so they're computed when `run_validation=True`, and added the combined `verdict` to the validation dict.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-simulator/vinu_simulator/engine/validation.py` | vinu-simulator | modify — added 3 new functions |
| `vinu-simulator/vinu_simulator/service.py` | vinu-simulator | modify — wired new functions and verdict into `_run_validation_and_attribution` |
| `vinu-simulator/tests/test_validation.py` | vinu-simulator | create — 24 new tests |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-block-bootstrap.md` | Implement block_bootstrap_permutation | DONE |
| 2 | `02-task-price-path-resample.md` | Implement price_path_resample | DONE |
| 3 | `03-task-verdict-combiner.md` | Implement compute_validation_verdict | DONE |
| 4 | `04-task-wire-service.md` | Wire new functions into service.py | DONE |
| 5 | `05-task-tests.md` | Write comprehensive tests | DONE |

## Dependencies Met

- [x] No dependencies — pure math, built in parallel with Steps 1–2

## Verification

- [x] All 24 new tests pass
- [x] All 97 existing vinu-simulator tests pass — zero regressions
- [x] Boundary cases tested: insufficient data, edge-of-threshold, empty inputs, RNG reproducibility

## Review Findings & Fixes Applied (2026-07-24, separate review session)

An independent review found two issues, both in `compute_validation_verdict`'s handling of the
"no data" case:

- **Fail-open bug**: when every sub-check (`monte_carlo`, `block_bootstrap`, `price_path`,
  `walk_forward`, `bootstrap`) reported `minimum_met: False` (i.e. not enough trades/observations
  to run any statistical test at all), `all_passed` stayed at its initial `True` — nothing in the
  loop ever sets it `False` for the all-skipped case, since the `else` branches only append a
  "skipped" reason. Net effect: a strategy with too little data to validate **passed the gate by
  default** instead of being held back pending more data — exactly backwards for something
  described as a hard, un-bypassable gate.
  - **Test masked it**: `test_skips_insufficient_data_sub_results` asserted
    `verdict["passed"] is True` for this exact scenario, i.e. the test encoded the bug as the
    spec rather than catching it.
  - **Fix**: added an `any_method_ran` tracker set `True` whenever any sub-check's
    `minimum_met` is `True`; if it's still `False` after checking every sub-result, `all_passed`
    is forced to `False` with an explicit reason. Renamed the test to
    `test_fails_closed_when_every_method_has_insufficient_data` and fixed its assertion; added a
    new `test_passes_when_some_methods_skip_but_the_rest_pass` to keep the (correct, still
    supported) partial-skip case covered — a strategy shouldn't be blocked just because one
    method (e.g. block-bootstrap needing ≥3 trades) couldn't run while everything else passed.
- **Cache-hash bug (pre-existing, not introduced by this phase, but in the same subsystem)**:
  `SimulatorService`'s config-hash computation in both `simulate()` and `_simulate_custom_impl()`
  still excluded `req.run_validation` from the hashed params. A request with
  `run_validation=True` could get a cache hit against a previously-cached run that never computed
  validation, silently returning `validation: None` instead of actually validating. Fixed by
  adding `"run_validation": req.run_validation` to both hash dicts, and made
  `_reconstruct_result` (the cache-hit path) carry `validation=row.get("validation")` onto the
  reconstructed `SimulationResult` so a legitimate cache hit (matching `run_validation` flag)
  still returns validation correctly.
- **Suite after fix**: 126/126 vinu-simulator tests pass (122 + 4 new persistence-round-trip
  tests from the Phase 04 fix below).
