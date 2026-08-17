---
task: 06-walk-forward-validation.md
status: complete
---

# Status: task 06 — add walk-forward validation next to the existing PBO check

## Audit first (verify-before-build)

The plan's "Current state" said *no walk-forward equivalent exists anywhere in
`vinu-research`*. That was stale. Verified present and already wired:

- `vinu-research/vinu_research/walk_forward.py` — `WalkForwardConfig`, `WindowSplitter`,
  `aggregate_metrics`, plus the loop's *snapshot* walk-forward (`_run_walk_forward` in `loop.py:765`,
  enabled via `config.walk_forward_enabled`, PBO also computed at `loop.py:631-653`), and a
  `WalkForwardResult` model (`models.py:536`, `has_walk_forward` at `:547`).
- `report.py` rendered an "OUT-OF-SAMPLE VALIDATION" section (`:215+`) with IS/OOS/gap prose verdicts.

The real gaps (what this task closed):

1. No *parameter-re-optimizing* walk-forward for the recipe/grid path — the snapshot walk-forward tests
   a single fixed strategy's params across OOS windows; the task's literal ask ("re-optimizes parameters
   per window" + stability metric) and the Jarvis reference were not covered.
2. Role c's recipe-path self-verdict (`run_parameter_sweep` → backtest_runner Path B) read completeness
   + PBO only; walk-forward stability was NOT in the evidence.
3. The report's stability threshold was hardcoded (0.5/0.3).
4. No N-of-M window-completeness reporting (only `n_windows` completed).

## What I did

- `vinu-research/vinu_research/walk_forward.py` — added:
  - `WalkForwardRunWindow` / `WalkForwardRunResult` dataclasses (`to_dict()`), with `n_planned`,
    `n_completed`, `completeness` (N-of-M windows), `sharpe_gap`, `oos_positive_window_fraction`,
    `parameter_agreement`, and `stability_verdict`.
  - `evaluate_walk_forward_stability(...)` — deterministic PASS/FAIL, fail-closed (incomplete run, too
    few completed windows, Sharpe gap past the configurable threshold, or <50% of OOS windows
    profitable all push FAIL).
  - `async run_walk_forward(symbol, from_date, to_date, param_grid, recipe/base_code, ...)` — per
    rolling window it re-optimizes the grid on the train slice via `run_sweep_grid` and backtests the
    window's best params out-of-sample via `run_sweep_candidate`, i.e. the exact same backtest
    execution path as the sweep engine (vinu-simulator), no separate runner. Returns `None` when there
    isn't enough data for one window (same posture as the loop's snapshot walk-forward). Inner window
    grids pass `dataclasses.replace(config, walk_forward_enabled=False)` so it never recurses.
- `vinu-research/vinu_research/sweep_grid.py` — `SweepGridResult` gains `walk_forward: dict | None`;
  `run_sweep_grid` runs `run_walk_forward` when `config.walk_forward_enabled` and `ranked` is non-empty
  (lazy import, guarded, failure logged not fatal). Added `sweep_evidence_verdict(completeness, pbo,
  walk_forward, *, completeness_tolerance=0.95, pbo_severe=0.7)` — the single deterministic
  PASS/FAIL gate that folds all three evidence signals; a walk-forward stability FAIL is an automatic
  overall FAIL even when PBO is clean.
- `vinu-research/vinu_research/config.py` — new knobs: `walk_forward_stability_threshold` (0.5, env
  `VINU_RESEARCH_WF_STABILITY_THRESHOLD`) and `walk_forward_min_completed_windows` (2, env
  `VINU_RESEARCH_WF_MIN_COMPLETED_WINDOWS`).
- `vinu-research/vinu_research/report.py` — `generate_report(...)` accepts
  `walk_forward_stability_threshold=0.5`; the HIGH/MODERATE prose bands use the config threshold
  (moderate = threshold * 0.6) instead of hardcoded 0.5/0.3. `loop.py` passes the config value.
- `vinu-research/vinu_research/server/routes_sweep.py` + `vinu-agent/vinu_agent/tools/run_parameter_sweep_tool.py`
  — `_serialize_grid` / `_serialize_sweep_grid` now carry the `walk_forward` block in the sweep result.
- `vinu-agent/teams/research/agents/backtest_runner/prompt.md` — Path B documents the `walk_forward`
  block (sharpe_gap, oos_positive_window_fraction, parameter_agreement, stability_verdict), and adds
  the rule: `walk_forward.stability_verdict.passed == false` is an **automatic FAIL** even when
  completeness and PBO look fine; a `null` walk_forward is stated as "no walk-forward evidence," not a
  clean pass.

## What is achieved

- `run_walk_forward` is a real, testable, module-level function on the recipe path that re-optimizes
  parameters per rolling window, shares the sweep engine's backtest path, and reports both parameter
  stability (`parameter_agreement`) and OOS performance stability (`sharpe_gap`,
  `oos_positive_window_fraction`) with a deterministic verdict.
- The recipe-path self-verdict now reads PBO **and** walk-forward stability; a candidate that passes PBO
  but fails walk-forward stability produces an overall FAIL (`sweep_evidence_verdict` + prompt rule) —
  additive coverage proven by `test_pbo_pass_but_walk_forward_fail_is_overall_fail`.
- The stability threshold is configurable via config/env, not hardcoded.
- Window completeness follows the sweep-engine N-of-M pattern; partial/failed runs fail closed.

## Testing

- `vinu-research/tests/test_walk_forward.py` — `TestEvaluateWalkForwardStability` (stable passes; large
  gap fails; threshold configurable; incomplete run fails closed; too-few-windows fails; mostly-losing
  OOS fails), `TestRunWalkForward` (stable params → PASS verdict; params flipping + collapsing OOS →
  FAIL with the exact reasons; partially-failed windows count against completeness; insufficient data →
  `None`), `TestSweepEvidenceVerdict` (all-clean PASS; PBO-pass + walk-forward-FAIL → overall FAIL;
  low completeness → FAIL; severe PBO → FAIL; missing walk-forward stated, not silently passed).
- `vinu-research/tests/test_sweep_grid.py` — `TestRunSweepGridWalkForwardWiring` (walk-forward attached
  when enabled, skipped when disabled, `_serialize_grid` carries it).
- Suites: `vinu-research/tests` **628 passed, 1 skipped**; `vinu-agent/tests` **830 passed**.
  (`test_run_parameter_sweep_tool` fixture updated with the new `walk_forward` field.)

## Alignment with plan

- Steps 1-5 of the task all covered: read Jarvis reference, reused the existing sweep backtest path,
  implemented `run_walk_forward` (matching the `run_parameter_sweep` convention), wired it into role c's
  self-verdict fail-closed, and followed the `completeness` N-of-M pattern.
- Acceptance criteria met: real testable function with stable vs unstable coverage distinguishable from
  PBO; self-verdict reads both with a PBO-pass/WF-fail → FAIL test; threshold configurable.

## Notes / gaps left

- The loop's snapshot walk-forward (`WalkForwardResult`) and the new recipe-path re-optimizing walk-forward
  (`WalkForwardRunResult`) are intentionally separate; they serve different code paths (raw strategy vs.
  recipe grid). The snapshot path already had its own N-of-M-free `n_windows` reporting; the recipe path
  now has full N-of-M completeness.
- Walk-forward adds latency to a sweep grid call (grid × windows re-optimizations); it's gated on
  `walk_forward_enabled` (default true) and failure is logged, never fatal to the sweep result.