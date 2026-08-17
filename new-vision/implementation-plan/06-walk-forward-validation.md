---
name: walk-forward-validation
closes: shortcoming #8 in ../01-vinu-components-shortcomings.md
ports: walk-forward validation logic, per ../02-reference-repos-core-logic.md
status: done
---

# Task: add walk-forward validation next to the existing PBO check

## Goal

Researcher/Executor's role c (self-verdict) already has `pbo.py`'s overfitting-probability check. Add
walk-forward validation as a second, complementary gate in the same self-verdict step.

## Why

PBO (probability of backtest overfitting) and walk-forward validation catch different failure modes —
PBO estimates the odds a strategy's apparent edge is an in-sample artifact; walk-forward tests whether the
optimal parameters found actually hold up when re-optimized on rolling out-of-sample windows. Confirmed
during the reference-repo comparison that this is a genuine gap, not redundant with PBO.

## Current state (verified 2026-08-17 — re-check before building)

- `vinu-research/vinu_research/pbo.py` — built, real, used in role c's self-verdict (confirmed wired via
  the sweep-grid call chain: `sweep_grid.py` → `rank_candidates` → role c reads the ranked table plus
  PBO). This is the pattern to extend, not replace.
- No walk-forward equivalent exists anywhere in `vinu-research` — confirmed absent by the original
  shortcomings audit.
- Reference implementation to port from: `Jarvis/core/backtesting/walk_forward.py` and the adjacent
  `monte_carlo.py`, `parameter_optimizer.py` in the same directory
  (`/home/somic_cps/Vina/my-trading-work-3/personal-important/other-reference-repos/Jarvis/core/
  backtesting/`). Real, deployed code — port the validation logic, not the surrounding Jarvis-specific
  scaffolding (its data ingestion, its own artifact model, etc.).

## Steps

1. Read `Jarvis/core/backtesting/walk_forward.py` in full to understand its exact windowing approach
   (rolling vs. anchored, how many folds, what stability metric it reports).
2. Read `vinu-research/vinu_research/sweep.py` and `sweep_grid.py` to understand how the existing sweep
   grid is structured (parameter ranges, the backtest runner it calls per candidate) — walk-forward needs
   to reuse the same backtest execution path (`run_backtest`/vinu-simulator, already used elsewhere in
   this pipeline), not a separate one.
3. Implement a `run_walk_forward(recipe, param_grid, ...)` function in `vinu-research` (naming should
   match the existing `run_parameter_sweep` convention) that: splits the historical data into rolling
   train/test windows, re-optimizes parameters per window, and reports a stability metric (e.g. how much
   the optimal parameters and their out-of-sample performance vary window to window).
4. Wire this into role c's self-verdict alongside the existing PBO read — same fail-closed posture as the
   sweep-completeness check: below-threshold walk-forward stability should push toward FAIL, not a
   lenient PASS off a single lucky window.
5. Follow the existing `completeness` field pattern from the sweep engine (N of M grid points actually
   succeeded) — walk-forward should report an equivalent (N of M windows actually completed) so a
   partial/failed run can't silently masquerade as a full pass.

## Acceptance criteria

- `run_walk_forward` is a real, testable function with unit tests covering: stable-parameters case
  (should report high stability), unstable/overfit case (should report low stability and be
  distinguishable from the PBO signal on the same synthetic data).
- Role c's self-verdict reads both PBO and walk-forward stability, and a test confirms a candidate that
  passes PBO but fails walk-forward stability produces an overall FAIL (proving this is additive, not
  redundant, coverage).
- The exact stability threshold is configurable, not hardcoded — matching the design doc's own
  "Open questions" stance that tuning parameters like this need real data, not guesses.

## Dependencies

None, but pairs naturally with task 05 (position sizing) — both feed the same underlying question of
"how much do we actually trust this candidate's edge."
