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
| [04-daily-plan-document](04-daily-plan-document.md) | D4 | Not Started | — | — |
| [05-risk-budget](05-risk-budget.md) | D5 | Not Started | — | — |
| [06-agent-integration](06-agent-integration.md) | D6 | Not Started | — | — |
| [07-validation](07-validation.md) | D7 | Not Started | — | — |

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

*(No entries yet.)*

### 05-risk-budget (D5)

*(No entries yet.)*

### 06-agent-integration (D6)

*(No entries yet.)*

### 07-validation (D7)

*(No entries yet.)*

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
