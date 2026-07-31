---
name: AGENTS
status: living-document
purpose: mandatory progress log — every agent that touches a step must update this file
---

# AGENTS.md — Execution Log for Steps-to-Implement-Plan-2

This file is not a plan document — `00-overview.md` and the step files are
the plan. This file is the **record of what actually happened** when someone
executed a step: which files were touched, what was tested, what the result
was. If `00-overview.md` answers "what should we do and why," this file
answers "what has actually been done so far, by whom, and does it work."

Any agent picking up this project cold should read `00-overview.md` first
for context, then read this file to know the *real* current state —
because a step file's own `status:` frontmatter can drift out of date if
someone forgets to update it in two places. Treat this file as the
source of truth for "is X actually done," over memory, over assumption,
over the step file's frontmatter alone.

## Rules

1. **Update this file in the same turn you finish (or pause) work on a
   step.** Not "later," not "next session." If you did the work and didn't
   log it here, the next agent has no way to know it happened.
2. **One entry per work session per step**, appended under that step's
   section below — do not overwrite or delete a previous entry. This file
   is a log, not a snapshot. If a step is touched five times before it's
   done, there are five entries.
3. **Every entry states, at minimum:** date, status after this session,
   files touched (exact paths), tests/checks actually run (command +
   result, not "should work"), and anything the next agent needs to know
   (blockers, surprises, decisions made).
4. **"Tested" means you ran something and saw the output**, not that the
   code looks correct. If nothing was runnable yet (e.g. pure design/doc
   work), say `No test applicable — design/doc only` explicitly rather
   than leaving the field blank. A blank field is indistinguishable from
   "forgot to fill it in."
5. **Update the status table below AND the step's own frontmatter AND
   `00-overview.md`'s phase table.** All three must agree. This file's
   table is the fast-scan summary; the entries below it are the evidence
   for why the table says what it says.
6. **Never mark a step `Completed` unless its Definition of Done checklist
   (in that step's own file) is fully checked.** If most of it is done but
   not all, the status is `In Progress`, not `Completed`. Partial credit
   goes in the entry's notes, not in the status column.
7. **If you discover a step file's plan was wrong or incomplete once you
   actually did the work**, record that under that entry's notes and update
   the step file itself. Do not silently diverge from the written plan
   without leaving a trace of why.

## Status values

- `Not Started` — nothing done yet.
- `In Progress` — actively being worked; see latest entry for what's left.
- `Blocked` — see latest entry for what it's blocked on and which step.
- `Completed` — Definition of Done checklist fully checked, verified in an
  entry below, not just claimed.

## Status table

| Step | Code | Status | Last updated | Files touched (this run) |
|---|---|---|---|---|---|
| [01-stage-skills](01-stage-skills.md) | D1 | Completed | 2026-07-31 | See entry below |
| [02-shock-clustering](02-shock-clustering.md) | D2 | Completed | 2026-07-31 | See entry below |
| [03-probabilistic-exit](03-probabilistic-exit.md) | D3 | Completed | 2026-07-31 | See entry below |
| [04-daily-plan-document](04-daily-plan-document.md) | D4 | Completed | 2026-07-31 | See entry below |
| [05-risk-budget](05-risk-budget.md) | D5 | Completed | 2026-07-31 | See entry below |
| [06-agent-integration](06-agent-integration.md) | D6 | Completed | 2026-07-31 | See entry below |
| [07-validation](07-validation.md) | D7 | In Progress | 2026-07-31 | See entry below |

*(Keep this table's "Last updated" and "Files touched" columns short —
one line, most recent session only. Full history lives in the per-step
entries below.)*

---

## Entries

*(Append new entries under the matching step's heading. Do not delete old
entries. Newest entry at the top of each step's section.)*

### 01-stage-skills (D1)

#### 2026-07-31 Completed

- **Files touched:**
  - Copied: `project-understanding/skills/` → `vinu-agent/skills/` (7 dirs: gatekeepers, strategy-tags, vinu-tools-catalog, optimizer-rules, governor, live-safety, daily-allocation)
  - `vinu_agent/agent/skills.py` — fixed `read_text` encoding to utf-8
  - `vinu_agent/broker/performance_store.py` — created PaperPerformanceStore
  - `vinu_agent/server/routes_broker.py` — added GET/POST `/broker/performance/{artifact_id}`
  - `vinu_agent/config.py` — added `vinu_live` to services dict
  - `vinu_live/shadow_evaluator.py` — fixed 2 missing `await` on `resp.json()`
  - `vinu-live/tests/test_shadow_evaluator.py` — created (3 tests)
  - `vinu-live/vinu_live/cli.py` — added shadow-evaluate command
  - `vinu-live/vinu_live/server/app.py` — added `/live/shadow-evaluate` route
  - `vinu-agent/tests/test_routes_broker.py` — added 3 performance endpoint tests
- **Tests/checks run:**
  - `pytest vinu-agent/tests/test_skills.py` — 15 passed
  - `pytest vinu-agent/tests/test_routes_broker.py` — 15 passed (+3 new)
  - `pytest vinu-live/tests/test_shadow_evaluator.py` — 3 passed (new)
  - SkillsLoader verify: 29/29 skills loaded, 7/7 staged found
- **Definition of Done progress:** all 5 checklist items checked.
- **Notes for next agent:**
  - Two latent bugs fixed in `shadow_evaluator.py`: `_list_benching_artifacts` line 55 and `_fetch_paper_sharpe` line 111 returned `resp.json()` without `await`, which would cause `TypeError: 'coroutine' object is not iterable` at runtime.
  - The performance data store is in-memory (v1). When shadow evaluation is scheduled in Step 07, consider persisting per-artifact daily returns to the research API's SQLite database.
  - `vinu_live` is now registered in `AgentConfig.services` at default URL `http://localhost:8091`.
  - The `shadow-evaluate` command is available via both CLI (`vinu-live shadow-evaluate`) and HTTP (`POST /live/shadow-evaluate`).

### 02-shock-clustering (D2)

#### 2026-07-31 Completed

- **Files touched:**
  - `vinu_portfolio/shock_correlation.py` — created (DCC-GARCH estimator, 120 lines)
  - `vinu_portfolio/service.py` — integrated `dcc_shock_correlation()` into `build_portfolio()`
  - `vinu-portfolio/tests/test_shock_correlation.py` — created (10 test cases)
- **Tests/checks run:**
  - `pytest vinu-portfolio/tests/test_shock_correlation.py` — 10 passed
  - `pytest vinu-portfolio/tests/` — 59 passed (49 existing + 10 new)
- **Definition of Done progress:** all 5 checklist items checked.
- **Notes for next agent:**
  - Uses existing `_garch_ml_estimate` from vinu-tools (no `arch` dependency added).
  - The DCC estimator is pragmatic v1: EWMA on GARCH-standardized residuals rather than full DCC likelihood optimization. The key improvement is that shock correlation is now computed portfolio-wide and included in `build_portfolio()` output alongside calm-day Pearson correlation.
  - The existing `shock_clustering` angle in vinu-initial-analysis still returns `"single_symbol"` when called via AngleRunner. The portfolio-level DCC estimator is the canonical source for shock correlation going forward. If the angle is also needed for multi-symbol results, that would require modifying AngleRunner to support batch mode (not done here).
  - Step 04 (daily plan document) can now consume `shock_correlation` from `build_portfolio()` output.

### 03-probabilistic-exit (D3)

#### 2026-07-31 Completed

- **Files touched:**
  - `vinu_research/vinu_research/probabilistic_exit.py` — created
  - `vinu-live/vinu_live/trade_plan/live_metrics.py` — added P_failure metric
  - `vinu-live/vinu_live/trade_plan/orchestrator.py` — added calibration fetch
  - `vinu-research/vinu_research/trade_plan_authoring.py` — added probability-based conditions
  - `vinu-research/tests/test_probabilistic_exit.py` — created (16 tests)
- **Tests/checks run:**
  - `pytest vinu-research/tests/test_probabilistic_exit.py` — 16 passed
  - `pytest vinu-research/tests/` — 536 passed, 1 skipped
  - `pytest vinu-live/tests/` — 118 passed
- **Definition of Done progress:** all 6 checklist items checked.
- **Notes for next agent:**
  - P_failure is computed at position evaluation time (not pre-computed). The orchestrator fetches calibration accuracy for each artifact when evaluating open positions. Caching can be added if the extra HTTP call per position becomes a concern.
  - The confidence decay assumes `created_at` on the TradePlan is the forecast time. If plans are re-fetched or regenerated, this may reset the decay — verify downstream.
  - `magnitude_std` and `horizon_days` defaults to 0 from the LLM. When 0, the formula degrades gracefully (neutral weights, no decay).

### 04-daily-plan-document (D4)

#### 2026-07-31 Completed

- **Files touched:**
  - `vinu_portfolio/service.py` — broadened `compute_daily_game_plan()`'s
    readiness-score formula to count regime and equity availability, not
    just trade-plan coverage
  - `vinu-portfolio/tests/test_game_plan.py` — updated existing readiness
    assertions to match the broadened formula, added
    `test_all_data_unavailable_edge_case` and
    `test_readiness_score_reflects_regime_and_equity_availability`
  - `vinu-portfolio/tests/test_e2e_pipeline.py` — updated one stale
    readiness-score assertion to match the broadened formula
  - `vinu-agent/skills/daily-allocation/SKILL.md` — added "Unified daily
    game plan" section documenting the merge and readiness formula
  - `steps-to-implement-plan-2/04-daily-plan-document.md` — filled in
    "What was actually built", checked DoD, flipped status to Completed
- **Tests/checks run:**
  - `PYTHONPATH="../vinu-tools:$PYTHONPATH" pytest vinu-portfolio/tests/ -q`
    — 95 passed (baseline 89 + 6 new tests across this entry and 05's)
- **Definition of Done progress:** all 6 checklist items checked.
- **Notes for next agent:**
  - The code that merges TradePlans into a unified document
    (`game_plan.py`, `compute_daily_game_plan()`, the route, and the CLI
    command) already existed uncommitted before this session — this entry
    is not "built from scratch," it's closing the two real DoD gaps
    (readiness formula scope, missing edge-case test) that were found by
    reading the actual code against the step file's DoD checklist, plus
    the doc that was never written.
  - The readiness score is now a genuine multi-source signal: this
    changes `readiness_score`'s numeric value and the `game_ready` gate's
    behavior for any caller relying on the old (trade-plan-only) formula.
    Confirmed with the user before making this change since it's
    production risk-signal behavior, not just a doc fix.

### 05-risk-budget (D5)

#### 2026-07-31 Completed

- **Files touched:**
  - `vinu-portfolio/tests/test_risk_budget.py` — added
    `test_regime_shift_tightening_is_distinct_from_budget_breach`,
    `test_regime_tightening_composes_multiplicatively_with_tier_reduce`,
    `test_halt_tier_zeroes_size_regardless_of_regime`,
    `test_daily_pnl_does_not_accumulate_across_repeated_calls`
  - `vinu-agent/skills/live-safety/SKILL.md` — added "Daily risk budget"
    section: tier table, the regime-tightening formula actually
    implemented vs. the research-notes formula, and the
    `DailyPositionTracker` production-wiring finding
  - `vinu-agent/skills/daily-allocation/SKILL.md` — added a short
    cross-reference section pointing to `live-safety/SKILL.md`'s detail
  - `steps-to-implement-plan-2/05-risk-budget.md` — filled in "What was
    actually built", checked DoD, updated "Open risks" with resolved
    findings, flipped status to Completed
- **Tests/checks run:**
  - `PYTHONPATH="../vinu-tools:$PYTHONPATH" pytest vinu-portfolio/tests/ -q`
    — 95 passed (see 04's entry; same run covers both steps' new tests)
- **Definition of Done progress:** all 6 checklist items checked.
- **Notes for next agent:**
  - `compute_risk_budget()`, `DailyPositionTracker`, the route, and the
    CLI command already existed uncommitted before this session, same
    situation as Step 04. This entry closes DoD gaps found by reading the
    code against the checklist and the step's own research notes.
  - **Two real findings, documented but deliberately not fixed:**
    (1) the implemented regime-tightening is a flat portfolio-wide
    multiplier (`REGIME_SIZING_MULTIPLIERS`), not the tag-alignment
    `alignment_score` formula from this step's own research notes — a v1
    simplification, not a bug, but a real scope gap from the original
    design. (2) `compute_risk_status()` constructs a fresh
    `DailyPositionTracker` on every call, so the tracker's
    accumulate-across-calls behavior — which it supports and is
    unit-tested doing in isolation — never actually fires in production;
    each response is just that call's `unrealized_pl` snapshot, not a
    true running intraday total. Both are pinned with regression tests
    and written up in `live-safety/SKILL.md` so they don't silently
    regress or get forgotten. Neither was fixed here — both change
    production risk-signal behavior and deserve their own deliberate
    review, not a side effect of a doc-reconciliation pass. Flagging for
    the user to decide whether either should be scoped as follow-up work.

### 06-agent-integration (D6)

#### 2026-07-31 Completed

- **Files touched:**
  - `vinu-agent/vinu_agent/tools/load_skill_tool.py`,
    `remember_tool.py`, `session_search_tool.py`, `complete_step_tool.py`,
    `plan_workflow_tool.py`, `query_memory_tool.py` — each now sets its
    private dependency attribute (`_skills_loader`, `_unified_memory`,
    `_session_service`, `_workflow_tracker`) to `None` in `__init__`,
    matching the existing `_services_config = {}` convention used by
    ~15 other tools
  - `vinu-agent/tests/test_tools_discovery.py` — added
    `test_build_registry_injects_skills_loader`,
    `_injects_unified_memory`, `_injects_session_service`,
    `_injects_workflow_tracker`, asserting the injected object is
    actually present on the tool after `build_registry(...)`, not just
    that construction doesn't crash
  - `vinu-agent/tests/test_agent_integration.py` — new file, end-to-end
    test using a real `build_registry()` + real `SkillsLoader` + real
    `AgentLoop`, scripted through `plan_workflow` → `load_skill` →
    `complete_step`, asserting real skill content is returned, the shared
    `WorkflowTracker` reaches `all_completed()`, and a live `<workflow>`
    block is actually injected into an LLM call mid-run; plus a
    negative-path test for an uninjected registry
  - `vinu-agent/skills/agent-self/SKILL.md` — added sections on how
    skills/workflow tools work at runtime, the DI bug + fix, and the
    governor Layer 1/Layer 2 tracing finding
  - `steps-to-implement-plan-2/06-agent-integration.md` — filled in "What
    was actually built", checked DoD (including the governor item, with
    rationale), flipped status to Completed
  - `steps-to-implement-plan-2/01-stage-skills.md` — added a 2026-07-31
    addendum cross-referencing this step's DI-bug finding, since it
    concerns Step 01's own "skills are usable" claim
- **Tests/checks run:**
  - `pytest vinu-agent/tests/ -q` — 224 passed (baseline 218 + 4 DI
    regression tests + 2 new integration tests)
  - Manual check per the audit plan's verification section: instantiated
    `build_registry(skills_loader=fake, unified_memory=fake,
    session_service=fake, workflow_tracker=fake)` and asserted each of
    the 6 tools' private attribute `is` the fake object — confirmed.
- **Definition of Done progress:** all 6 checklist items checked, including
  the governor item — see "What was actually built" in the step file for
  why that's checked without new governor code being written.
- **Notes for next agent:**
  - **Root cause of the bug:** `build_registry()`
    (`vinu_agent/tools/__init__.py`) only injects a dependency when
    `hasattr(tool, "_x")` is already `True` *before* injection. Six
    tools (load_skill/remember/search_sessions/query_memory/complete_step/
    plan_workflow) only referenced their dependency via
    `getattr(self, "_x", None)` inside `execute()`, with no `__init__`
    setting a default — so `hasattr()` was `False` and injection silently
    never fired, even though `vinu_agent/session/service.py` was already
    passing real values into `build_registry()`. In production this meant
    the agent could not read skills, remember things, search sessions, or
    use the workflow tools at runtime, despite all the wiring code on the
    `service.py` side looking correct.
  - `query_memory_tool.py` had the identical bug pattern despite not
    being named in the original bug list — found by checking it directly
    as instructed, and fixed the same way.
  - This is directly relevant to Step 01's "Completed" status: Step 01
    verified skills are staged and *readable via `SkillsLoader` directly*,
    but never exercised the `build_registry()` injection path, so this
    bug was invisible to that step's own testing. Step 01's checklist
    items are still individually true; "skills are staged" and "skills
    are usable by the agent at runtime" were not, in fact, the same claim
    until this fix.
  - **Governor DoD item — traced, not built, and this is a deliberate
    call worth a second look if priorities change:** `governor/SKILL.md`
    (from the first plan's Step 08) already documents that its Layer 1
    hard limit *is* the ReAct loop's existing `max_iterations` cap, and
    that Layer 2's heuristics are intentionally agent-composed reasoning
    over existing tools, not loop-level code. Checked the DoD box on that
    basis rather than writing a new `governor.py` enforcement module. If
    a future need arises for the loop to mechanically enforce Layer 2
    (rather than trusting the agent to apply it), that's new scope beyond
    what this step or `governor/SKILL.md` currently call for — flag it
    explicitly rather than assuming it's already covered by this entry.
  - Wiring confirmed correct end-to-end by direct trace:
    `session/service.py::_run_with_agent` constructs one
    `WorkflowTracker()`, passes it into `build_registry(...)` for the
    tools, and also assigns it directly onto the `AgentLoop` instance —
    so the loop's context-block rendering and the tools' state mutation
    were always meant to share one object; the DI bug was the only thing
    breaking that chain in practice.

### 07-validation (D7)

#### 2026-07-31 In Progress

- **Files touched:**
  - `vinu_portfolio/historical_simulation.py` — new: walk-forward
    daily-rebalance simulator (`run_historical_simulation()`,
    `compute_performance_metrics()`, `fetch_historical_returns()`,
    `fetch_benchmark_returns()`)
  - `vinu-portfolio/tests/test_historical_simulation.py` — new, 12 tests
    against synthetic data
  - `vinu_portfolio/cli.py` — added `historical-simulate [--days N]`
    command
  - `steps-to-implement-plan-2/07-validation.md` — filled in "What was
    actually built" for substeps 1-3, documented the substep 4/5 blocker,
    checked 2 of 6 DoD boxes, status set to In Progress (not Completed)
- **Tests/checks run:**
  - `PYTHONPATH="../vinu-tools:$PYTHONPATH" pytest vinu-portfolio/tests/ -q`
    — 107 passed (95 + 12 new)
  - Confirmed (not assumed) that a real run isn't currently possible:
    `curl http://127.0.0.1:8081/health` fails to connect (no running
    `vinu-stock-price`); listed `vinu-stock-price/data/` and found no
    candle parquet/db files, only catalog/backfill metadata tables in
    `meta.db`.
- **Definition of Done progress:** 2 of 6 checklist items checked
  (script exists and runs / produces all planned metrics — both verified
  against synthetic data only). The remaining 4 (results documented,
  paper trading run, paper trading documented, final verdict) are
  genuinely blocked, not skipped: no historical price data exists to run
  a real simulation against, and `ShadowEvaluator` paper trading needs a
  live multi-day (1+ week) deployment window that no single session can
  provide regardless of what code exists.
- **Notes for next agent:**
  - **Do not report Step 07 as Completed or cite any performance number
    from it** — nothing here has been run against real data.
    `vinu_stock/backfill/` in the `vinu-stock-price` repo looks like the
    right starting point for getting real historical data in, but wasn't
    traced further this session — that's the actual next unblocking step
    before substep 4 can happen for real.
  - The simulator deliberately only replays the risk-parity + regime tilt
    (Step 10 + Step 04's addition), not outcome-confidence or
    shock-clustering tilts or the Step 04/05 game-plan/risk-budget
    layers — none of those have a historical trail to reconstruct from.
    See `historical_simulation.py`'s module docstring and this step
    file's "What was actually built" for the full reasoning.
  - The user was asked explicitly (via clarifying question) whether to
    build Step 07 now vs. defer it, and chose "build it now" — this
    entry is the result of that: real, tested code for the parts that
    are actually buildable in one session, honestly incomplete on the
    parts that require live data/infrastructure/elapsed time that don't
    exist here.

---

## Entry template (copy this when adding a new one)

```
#### [YYYY-MM-DD] <status after this session>

- **Files touched:** <exact paths, or "none — investigation only">
- **Tests/checks run:** <exact command + result, or "No test applicable — design/doc only">
- **Definition of Done progress:** <which checklist items in the step file are now checked>
- **Notes for next agent:** <blockers, surprises, decisions made, anything
  that diverged from the step file's original plan>
```
