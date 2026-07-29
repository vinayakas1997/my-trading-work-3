# Phase 6 — Integration Testing

Status: **not started** · Depends on: Phases 1–5 · Blocks: —

## What it is

A final pass that proves the whole pipeline works end to end, not just that each phase's unit
tests pass in isolation. By this point, Stages 0–3 all exist individually with their own test
coverage (specified in each phase's own document); this phase adds the tests that exercise
the *seams* between phases — the places most likely to break silently (a field renamed in
Phase 1 that Phase 4's query doesn't expect, a status value from Phase 2 that Phase 5's
renderer doesn't handle, etc.).

This phase also revisits one deliberately deferred decision: whether
`vinu-agent/vinu_agent/tools/backtest_tool.py` (the user-facing, ad-hoc backtest tool, distinct
from the pipeline's internal `vinu-research` backtest calls) should expose `run_validation`/
`validation_config` as explicit LLM-facing parameters, so a user can request Monte Carlo
validation manually outside the full pipeline without forcing that cost onto every casual
backtest call.

## Impact

**Before this phase:** Each phase has been individually tested and reviewed, but nothing
proves a strategy can actually flow through Stage 0 → 1 → 2 → 3 and come out the other side with
a coherent, fully-populated playbook. Integration bugs (schema drift between phases, a status
value one phase doesn't recognize) would only surface in production use.

**After this phase:** A repeatable end-to-end test exists that catches pipeline-seam
regressions automatically, and the pipeline is confirmed ready for real use.

## Where changes occur

- **End-to-end synthetic pipeline test** (new, location TBD at implementation time — likely a
  new `tests/test_pipeline_e2e.py` at the `vinu-research` or repo-integration test level):
  drive a synthetic strategy through Stages 0→1→2 using the real (not mocked) code paths of
  `StrategyResearchLoop.run()`, `ComparativeCritic.review()`, and the Phase 1
  validation/storage plumbing, against synthetic/deterministic price and trade data (reuse
  `vinu-simulator/tests/conftest.py`'s `synthetic_prices`/`synthetic_weights` fixture style).
  Assert:
  - A strategy that would obviously fail Monte Carlo (e.g. random-signal strategy) is rejected
    at Stage 0 and never reaches Stage 1's iteration budget.
  - A strategy that passes Stage 0 and refines to PASS in Stage 1 produces a well-formed,
    non-empty `list[ComparisonAngle]` from Stage 2.
  - All of Stage 0's validation dict, Stage 1's iteration history, and Stage 2's comparison
    angles are independently queryable afterward via their respective storage layers (SQLite
    rows exist, not just in-memory objects).

- **`TradePlanTool` end-to-end test**: given a fully-populated pipeline result (from the test
  above, or an equivalent fixture), assert the Phase 5 playbook renders every new section
  (drawdown-by-regime, long/short split, news checklist, timing profile, comparison-angle
  caveats) with real content, not placeholder/"N/A" text.

- **`vinu-agent/vinu_agent/tools/backtest_tool.py`**: add `run_validation`
  (and optionally `validation_config`) to the tool's LLM-facing `parameters` schema and to the
  payload constructed in `execute()`, so a user/agent can opt into Monte Carlo validation for
  an ad-hoc backtest outside the full research pipeline. Default remains `False` for this
  standalone tool — only the internal `vinu-research` pipeline (Phase 2) forces it on by
  default, to avoid imposing validation cost on every casual backtest call.

## How to test it

- The end-to-end pipeline test and `TradePlanTool` test described above *are* the primary
  deliverable of this phase — they should be added to CI so pipeline-seam regressions are
  caught automatically on every future change to any of the five services touched by Phases
  1–5.
- Regression test for `backtest_tool.py`: confirm that omitting `run_validation` in a tool call
  still defaults to `False` (no behavior change for existing callers), and that explicitly
  passing `run_validation: true` results in a `"run_validation": true` key in the POST payload
  to `/simulate/custom`.
- Manual walkthrough: run one real (not synthetic) candidate strategy through the full pipeline
  via whatever entry point Phase 2 exposes, and read the resulting Stage 3 playbook end to end
  as a sanity check that the guidance reads coherently to a human, not just that fields are
  non-empty.
