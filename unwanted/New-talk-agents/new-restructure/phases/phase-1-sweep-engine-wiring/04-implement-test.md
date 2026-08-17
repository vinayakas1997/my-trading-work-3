---
name: phase-1-implement-test
status: built -- Phase 1 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 1 -- Implementation record

Built 2026-08-11, directly following Phase 0 in the same session.

## Real gap found beyond the original plan

`01-plan.md` assumed `backtest_runner`'s self-verdict could just "read...
`pbo.py`'s overfitting probability" as a pluggable step. Reading the real
code chain (`ResearchTools.run_backtest` -> `/simulate/custom` ->
`CustomSimulateResponse`) showed the HTTP response never carried a
per-period returns series at all -- only summary metrics and an
`equity_points` count. `pbo.py`'s `probability_of_backtest_overfitting`
needs a real `returns_matrix` (multiple candidates' per-period returns)
to compute anything; without this, "PBO" would have had to be faked or
skipped. Fixed by adding `daily_returns` to the simulator's response
(engine-level data already existed, `result.daily_returns`, it just
wasn't serialized) -- same "add the one real missing piece rather than
stub around it" approach as Phase 0's `latest-run` endpoint.

A second real gap, found while wiring the ranked table back to
`backtest_runner`: `comparison.rank_candidates()` returns `RankedCandidate`
objects wrapping only an `LlmCandidate` (code/params/reasoning) + scores --
it never carried the originating `run_id`/real metrics/trade_count. A
ranked table with no real numbers attached would have been useless to
report. Fixed with a new `RankedSweepCandidate` (in `sweep_grid.py`) that
re-attaches each ranked entry to its original `SweepCandidateResult` via
an id()-keyed lookup, without changing `comparison.py`'s own shape (still
used elsewhere for the non-grid ranking path).

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-simulator/vinu_simulator/server/schemas.py` | modified | `CustomSimulateResponse.daily_returns: list[float]` — additive field. |
| `vinu-components/vinu-simulator/vinu_simulator/server/routes_read.py` | modified | `simulate_custom()` populates `daily_returns` from `result.daily_returns.fillna(0.0).tolist()`. |
| `vinu-components/vinu-simulator/tests/test_custom_simulate_response_daily_returns.py` | new | 3 tests. Found and corrected a wrong assumption mid-build: the engine already drops the first (undefined) pct_change row rather than NaN-filling it, so `len(daily_returns) == equity_points - 1`, not `== equity_points`. |
| `vinu-components/vinu-research/vinu_research/sweep_grid.py` | new | `run_sweep_grid()` -- loops `run_sweep_candidate` over a bounded `param_grid`, ranks via `comparison.rank_candidates`, computes PBO via `pbo.probability_of_backtest_overfitting` across successful candidates' real return series, enforces `MAX_GRID_POINTS` (default 20, env-configurable via `VINU_RESEARCH_SWEEP_GRID_MAX_POINTS`) as a hard reject (never silent truncation). `completeness` denominator is always the requested grid size. |
| `vinu-components/vinu-research/tests/test_sweep_grid.py` | new | 10 tests -- every case from `03-test.md`'s completeness/grid-cap/ranked-table sections, plus the run_id/metrics-linkage regression test written after finding the gap above. |
| `vinu-components/vinu-research/vinu_research/server/routes_sweep.py` | modified | New `POST /sweep/grid` route + `SweepGridRequest`/`_serialize_grid`. Reuses the existing router (`app.py` needed no change -- same `router` object). |
| `vinu-components/vinu-research/tests/test_routes_sweep_grid.py` | new | 3 route-level tests (ranked table shape, oversized-grid 422, both-modes 422), mocked `ResearchTools` swapped in after `create_app()` via the existing `set_tools()` hook. |
| `vinu-components/vinu-agent/vinu_agent/tools/run_parameter_sweep_tool.py` | new | `RunParameterSweepTool` -- calls `/research/sweep/grid`. Longer timeout (600s) than the single-candidate tool, since one call now runs up to `MAX_GRID_POINTS` real backtests. |
| `vinu-components/vinu-agent/tests/test_run_parameter_sweep_tool.py` | new | 6 tests, mirroring `test_run_sweep_candidate_tool.py`'s existing style. |
| `vinu-components/vinu-agent/teams/research/agents/idea_generator/AGENT.md` | modified | Added `list_sweep_recipes` to `tools:`. |
| `vinu-components/vinu-agent/teams/research/agents/idea_generator/prompt.md` | modified | New "Default path: try a recipe first" section (RECIPE/PARAM_GRID output shape, real-data-grounded fit requirement) ahead of the existing raw-Python section, now labeled the exception path. |
| `vinu-components/vinu-agent/teams/research/agents/backtest_runner/AGENT.md` | modified | Added `run_parameter_sweep` to `tools:` (kept `run_backtest`). |
| `vinu-components/vinu-agent/teams/research/agents/backtest_runner/prompt.md` | modified | Branches on Path A (raw code, unchanged) vs. Path B (recipe grid, new) -- Path B requires a `SELF-VERDICT: PASS/FAIL` citing completeness (< 0.95 auto-FAIL) and PBO (≥ 0.5 flagged, ≥ 0.7 severe) before handoff. |
| `vinu-components/vinu-agent/teams/research/manager_prompt.md` | modified | New step ordering: forwards whichever shape idea_generator returned unchanged; on Path B, checks backtest_runner's SELF-VERDICT before spending a `risk_critic` call; SELF-VERDICT FAIL treated like a risk_critic STOP. Round-cap note: sweep-refine narrowing shares the one existing iteration budget, no separate counter. |
| `vinu-components/vinu-agent/tests/test_phase1_sweep_tool_scoping.py` | new | 5 tests walking the REAL `teams/` directory (not fixtures) -- confirms `list_sweep_recipes`/`run_parameter_sweep`/`run_sweep_candidate` are globally discoverable via `build_registry()` but the only two `AGENT.md` files listing any of them are `research/idea_generator` and `research/backtest_runner`. |

## Design deviations from `01-plan.md`, and why

- **Grid loop runs server-side (vinu-research), not client-side (vinu-agent).** The plan's "loops `run_sweep_candidate` internally... in a single tool call" was read as: the LLM's round-trip count is 1. Implemented as ONE new HTTP endpoint (`/sweep/grid`) that loops in-process, rather than vinu-agent making N sequential HTTP calls to the existing `/sweep/candidate` endpoint — avoids N real network round-trips for what should be one bounded unit of work, and keeps `run_sweep_candidate` itself unchanged (still the single-point primitive `sweep.py`'s docstring describes).
- **`backtest_runner`'s self-verdict uses fixed, stated thresholds** (completeness 0.95, PBO 0.5/0.7) rather than leaving them fully open — the guard rail only required "an explicit, stated tolerance," these are that tolerance, written into the prompt so they're visible/reviewable rather than an implicit LLM judgment call. PBO's 0.5/0.7 bands are `pbo.py`'s own documented interpretation (Bailey et al.), not invented here.
- **Explicit `param_grid` (list of dicts) instead of a range-expansion mini-language** (`{param: [start, stop, step]}`). Considered and rejected as unnecessary added surface for this phase — an LLM can write out a handful of coarse grid points directly in JSON, and an explicit list is far less likely to have an off-by-one/expansion bug than a parser this phase would also have to build and test.

## Test results

```
vinu-simulator:  129 passed (full suite, includes 3 new daily_returns tests)
vinu-research:   571 -> 581 passed (full suite; 10 new sweep_grid + 3 new routes_sweep_grid tests; 1 pre-existing skip, unrelated)
vinu-agent:      479 -> 490 passed (full suite; 6 new tool tests + 5 new scoping tests)
```

No regressions in any of the three packages' full suites.

## Real-LLM connectivity check

Ran one direct call through the actual configured OpenRouter client
(`create_llm_from_config` -> `google/gemma-4-31b-it:free`): resolved a
real context window of 262144 (confirms `/models` introspection works
against OpenRouter, not just local llama.cpp), got a real completion back
after one internal rate-limit retry (`RateLimitError, retrying in 1.0s,
attempt 1/3` -> succeeded). This is direct, live confirmation of the
free-tier rate-limit risk flagged in Phase 0's own implementation
record -- the existing retry logic in `agent/llm.py` absorbed it without
failing, but any phase running multiple back-to-back LLM calls (this one
included -- `idea_generator` -> `backtest_runner` -> `risk_critic`, each
a real call) should expect occasional retries under load, not treat one
as a bug.

## Known follow-ups (not blocking, not silently dropped)

- **The recipe-selection and self-verdict PROMPT behavior are not yet
  verified against a real live agent run** (only unit/route tests with
  mocked LLM-adjacent boundaries were run this pass) -- `test_idea_
  generator_prefers_recipe_when_fit_exists` and `test_idea_generator_
  falls_back_to_raw_code_when_no_recipe_fits` from `03-test.md` need an
  actual multi-turn research-team session against the configured
  OpenRouter model to confirm the new prompt text is followed correctly,
  not just well-formed. Deferred rather than run in this pass given the
  free-tier rate-limit risk just confirmed above and the real cost of a
  multi-agent session (idea_generator -> backtest_runner -> risk_critic,
  each a real LLM call, possibly several rounds) -- worth running
  deliberately, once, rather than folded into this implementation pass.
- **No retroactive re-validation was touched, confirmed by omission**: no
  code in this phase reads or rewrites any existing `SqliteStrategyStore`
  artifact row -- `test_no_retroactive_revalidation_of_existing_artifacts`
  from `03-test.md` is trivially satisfied (nothing in this diff could
  affect it) rather than needing its own new test.
- `MAX_GRID_POINTS` (20) and the completeness/PBO thresholds (0.95 / 0.5 /
  0.7) are first-pass, defensible defaults, not tuned against real trading
  outcomes yet -- revisit once real sweep rounds have run.
