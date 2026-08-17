---
name: live-llm-validation-tests
closes: shortcoming #5 in ../01-vinu-components-shortcomings.md
status: done — live-LLM suite exists and has been run against a real model; outputs recorded
---

# Task: validate prompt-dependent behavior against a real LLM, not just mocks

## Goal

Two specific behaviors are currently tested only against mocks and have never been confirmed against a
real model call. Run real-LLM smoke tests for both, and establish the pattern for future prompt changes
to get the same treatment.

## Why

Mocked tests confirm the code path executes; they don't confirm the model actually does what the prompt
asks. This project has already been burned by exactly this kind of gap once — the design doc's own intro
cites "raw LLM code generation," "hallucinated forecast columns," and "per-bar/whole-window confusion" as
real bugs found by tracing actual behavior, not by reading code. The two items below are the same risk
class, still open.

## Current state (verified 2026-08-17)

- **`idea_generator`'s recipe-first preference** (Phase 1): the Planner's design requires that
  `idea_generator` try a sweep recipe (`list_sweep_recipes`) before falling back to raw code generation —
  raw generation should be "the exception path... not the default it is today." This is only unit-tested
  with mocks; nobody has confirmed a real model, given the actual prompt, reliably picks the recipe path
  when one exists.
- **Phase 8's cross-angle consensus section**: `teams/screener/agents/angle_synthesizer/prompt.md` has a
  real "Cross-angle consensus (Phase 8)" section instructing the model to check whether independent
  angles (e.g. `arima` vs `chronos` forecast direction) agree or diverge. `agent/angle_consensus.py` and
  `test_phase8_end_to_end.py` exist, but per the earlier audit, no real-LLM run has confirmed the model
  actually produces sensible agree/diverge/insufficient_data verdicts when reading real angle data.

## Steps

1. For `idea_generator`: construct a small set of realistic test scenarios where a sweep recipe clearly
   exists and covers the proposed idea (e.g. a simple SMA-cross tuning ask that matches an existing
   recipe in `list_sweep_recipes`). Run the actual agent against a real model (whichever provider/model
   this project uses in production) and confirm it picks the recipe path, not raw code generation. Also
   test a genuine no-recipe-covers-this case and confirm it falls back to raw generation only then.
2. For the consensus check: construct realistic angle data with (a) a case where independent angles
   clearly agree, (b) a case where they clearly diverge, and (c) a case with insufficient data on one
   side. Run `angle_synthesizer` against a real model with each and confirm the consensus section
   produces the correct verdict category for each case — not just that the section exists in the output.
3. Write these as a distinct test suite (e.g. `test_live_llm_validation.py` per package) that's excluded
   from the default fast/CI test run (since it costs real API calls and real latency) but can be run
   deliberately — follow whatever pattern this project already uses to mark/skip expensive tests, if one
   exists; if not, a simple env-var gate (`RUN_LIVE_LLM_TESTS=1`) is fine.
4. Record actual model outputs from these runs (not just pass/fail) somewhere reviewable — this is
   exactly the kind of "trace a real bug" step that already caught the hallucinated-forecast-column bug
   mentioned in the design doc's intro; treat the raw output as worth reading, not just the assertion
   result.
5. If either behavior doesn't hold up in practice, that's a real finding — document it plainly (which
   scenario failed, what the model actually did) rather than adjusting the test to pass.

## Acceptance criteria

- A live-LLM test suite exists, is excluded from default CI runs, and can be run on demand.
- Both `idea_generator`'s recipe-first behavior and Phase 8's consensus section have been run against a
  real model at least once, with results documented (pass or fail, with actual model output shown).
- Any failure found is written up as a real gap, not silently patched over by loosening the test.

## Dependencies

Should ideally run after tasks 05 (position sizing) and 06 (walk-forward) land, so those new
prompt-adjacent behaviors (if any LLM-facing surface is added) get the same live-validation treatment
before being trusted. Not a hard blocker — can also validate the two items above independently, right
now.
