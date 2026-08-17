---
name: phase-1-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving the recipe-first, sweep-driven loop replaces raw code-gen as the default without losing the exception path or the fail-closed guarantees.
---

# Phase 1 -- Test plan

**`test_idea_generator_prefers_recipe_when_fit_exists`**
Input: a hypothesis whose reasoning matches a `BUILTIN_RECIPES` shape
(e.g. a momentum-angle-driven idea against the momentum recipe).
Expected: `idea_generator` calls `list_sweep_recipes`, selects that
recipe plus a coarse parameter range, and does **not** emit raw
`generate_weights` code in its final answer.

**`test_idea_generator_falls_back_to_raw_code_when_no_recipe_fits`**
Input: a hypothesis with no matching recipe shape in `BUILTIN_RECIPES`.
Expected: `idea_generator` still emits raw strategy code (the exception
path is preserved, not removed), and its reasoning states explicitly that
no recipe fit -- proves this isn't a silent fallback.

**`test_run_parameter_sweep_returns_ranked_table_in_one_call`**
Input: a recipe + a parameter grid of, say, 12 points.
Expected: one tool call returns a single ranked table (via
`comparison.py`'s `rank_candidates`) covering all 12 points -- assert the
call count into `run_sweep_candidate` internally is 12, but the *LLM's*
round-trip count for this step is 1, not 12.

**`test_completeness_reflects_requested_grid_size_not_attempted`**
Input: a 10-point grid where `substitute_param_value` fails to
parameterize 2 of them.
Expected: `completeness == 0.8` (8/10), not `1.0` computed against a
silently-shrunk denominator of 8.

**`test_self_verdict_fails_closed_below_completeness_threshold`**
Input: a ranked table with a strong top Sharpe, but `completeness` below
the stated tolerance (e.g. 0.8 vs. a 0.95 threshold).
Expected: role c's verdict is `FAIL`, explicitly citing incomplete
coverage -- not a PASS off the good-looking top result.

**`test_round_cap_stops_sweep_refine_loop`**
Input: a candidate where each refine round keeps finding a "promising but
not quite there" region, N+1 rounds attempted.
Expected: the loop halts at exactly N rounds (same `max_iterations`
mechanism as the existing manager loop), returns whatever verdict the
last completed round produced -- does not continue past the cap even
though the LLM would otherwise keep refining.

**`test_grid_size_cap_bounds_a_single_round`**
Input: a parameter grid larger than the configured per-round cap.
Expected: `run_parameter_sweep` rejects the oversized request (or caps it
and reports the cap was hit) rather than silently running an unbounded
number of points -- this is a distinct limit from the round cap above and
must be tested separately, not assumed covered by it.

**`test_new_tools_scoped_to_research_team_only`**
Input: `screener` team's resolved tool list after `build_registry` changes
land.
Expected: `RunSweepCandidateTool` and `ListSweepRecipesTool` are **not**
present -- proves the registration didn't leak these tools to teams that
don't need them.

**`test_no_retroactive_revalidation_of_existing_artifacts`**
Input: an artifact created before this phase landed, with a raw-code-gen
provenance and no sweep/PBO evidence.
Expected: its stored verdict and provenance are unchanged after Phase 1
ships -- nothing in this phase touches existing rows.

## End-to-end

**`test_phase1_recipe_to_verdict_walkthrough`**
Input: a real hypothesis for a symbol with real angle data backing it,
matching an existing recipe.
Expected: `idea_generator` picks the recipe -> `run_parameter_sweep` runs
the grid and returns a ranked table with real `completeness` ->
`backtest_runner`'s self-verdict reads the ranked table plus `pbo.py`'s
overfitting probability and returns PASS with the real Sharpe/drawdown
numbers from the best-ranked candidate, not a fabricated summary. This is
the case that proves the fix actually addresses the original bug: the
final PASS is backed by a deterministic sweep result, not a single
hand-written `generate_weights` the LLM never verified against real data
column names.
