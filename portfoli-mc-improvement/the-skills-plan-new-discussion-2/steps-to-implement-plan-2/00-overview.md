---
name: 00-overview
status: living-document
purpose: entry point for any agent picking up this plan cold
---

# Pre-Live Readiness — Implementation Plan Overview

**If you are an agent reading this for the first time: start here, then check
[AGENTS.md](AGENTS.md) for the real current state (this table can drift out
of date — AGENTS.md's entries are the evidence), then open the step file for
whatever you're about to work on. Each step file is written to stand on its
own — you should not need the full discussion transcript
(`the-discusion-plan.md` or the earlier `the-sills-and-agentic-plan-discussion.md`)
to understand what to do, only to understand *how we got here* if you're curious.**

## What this plan covers

The first plan (Steps 01-10 in `steps-to-implement-plan/`) built the core
intelligence layer: tool wiring, gatekeepers, sweep engine, optimizer rules,
governor, live-safety doc, and the daily portfolio allocation engine. All of
that is **built and tested** but none of it is **usable by the running agent**
yet — skills sit in a staging directory, `ShadowEvaluator` is dormant, the
agent loop hasn't been taught to compose skills at runtime, and several gaps
identified in post-plan discussion remain unaddressed.

This plan closes every remaining gap **before live trading**:

1. **Staging → live.** Move the 7 staged skills into `vinu-agent/skills/` so
   the agent can actually read them. Wire `ShadowEvaluator` (built, dormant,
   no test file, no callers) so the live-safety chain is real.
2. **Shock clustering.** Fix `AngleRunner` feeding one symbol at a time, so
   `shock_clustering` returns meaningful multi-symbol data instead of always
   `"single_symbol"`. The calm-day correlation matrix hides crash correlations.
3. **Probabilistic exit.** Replace deterministic threshold exits with
   probability-scored exits using calibration data + forecast magnitude_std,
   informed by empirical research on optimal thresholds.
4. **Unified daily plan document.** Merge per-symbol TradePlans under
   `compute_daily_allocation()` into one combined daily artifact with a
   readiness score that surfaces degradation rather than hiding it.
5. **Daily risk budget.** Add soft intraday limits ("down 5% by noon → stop
   opening") and dynamic regime-tightened risk bands, informed by research
   on institutional risk budgeting practices.
6. **Agent integration.** Modify the ReAct loop so the agent actually
   composes skills at runtime instead of just having them on disk.
7. **Validation.** Historical backtest of the allocation + game plan system,
   plus paper trading via the now-wired `ShadowEvaluator`.

## The operating principle (same as Phase 1)

**Skills are a knowledge library, not scripts.** We do not write procedures
for the agent to mechanically execute. At runtime the agent composes four
things itself — knowledge (skills), tools (vinu-* services), memory (existing
stores), governor (limits + heuristics). Every step below either strengthens
one of these four ingredients or removes a reason the agent can't reach one
of them yet.

## What has changed since Phase 1

Three new realities shape this plan differently from the first:

1. **Web research is required in some steps.** The first plan could answer
   every design question by reading the codebase. Steps 02, 03, and 05 here
   have questions whose answers aren't in your code — optimal probability
   thresholds for exit, shock correlation models, institutional risk
   budgeting — and need targeted web research before code is written.
   Each such step has a dedicated **Research** subsection.

2. **The agent still can't use what was built.** The first plan delivered
   real code and real tests, but the skills live in
   `project-understanding/skills/`, not `vinu-agent/skills/`. The agent loop
   (`vinu_agent/agent/loop.py`) has never been modified to compose them.
   This plan is the first time we explicitly close the gap between "built"
   and "usable by the agent."

3. **No new services or infrastructure.** Everything in this plan extends
   existing code in existing repos. No new `vinu-*` services, no new
   databases, no new infrastructure. Every step is additive to what already
   runs and is already tested.

## The phase map

| Phase | Step file | Code | Depends on | Unlocks | Status |
|---|---|---|---|---|---|
| 1 | [01-stage-skills.md](01-stage-skills.md) | D1 | nothing | 02, 03, 06 | Completed |
| 2 | [02-shock-clustering.md](02-shock-clustering.md) | D2 | 01 | 04 | Completed |
| 2 | [03-probabilistic-exit.md](03-probabilistic-exit.md) | D3 | 01 | 04 | Completed |
| 3 | [04-daily-plan-document.md](04-daily-plan-document.md) | D4 | 02, 03 | 05 | Completed |
| 3 | [05-risk-budget.md](05-risk-budget.md) | D5 | 04 | 07 | Completed |
| 4 | [06-agent-integration.md](06-agent-integration.md) | D6 | 01 | 07 | Completed |
| 5 | [07-validation.md](07-validation.md) | D7 | 05, 06 | — | In Progress |

**Reading the table:** Phase 2's two steps (02, 03) can run in parallel —
both depend on 01 but not on each other. Phase 3's `04` needs both `02` and
`03` finished. Phase 4 (`06`) can start as soon as `01` is done — it's
independent of the game-plan work. Phase 5 (`07`) is the final gate before
live trading and needs everything else done.

## Status legend

Update the `status` field in each step file's frontmatter as work happens:
- `Not Started` — nothing done yet.
- `In Progress` — actively being worked, note what's left in the file's own
  progress log section.
- `Blocked` — say what it's blocked on, and by which step.
- `Done` — deliverable exists and the Definition of Done checklist is
  fully checked. Update this overview's phase table row too when a step
  flips to Done, so this file stays the fast-scan source of truth.

## How to use this folder if you are picking this up cold

1. Read this file fully.
2. Read [AGENTS.md](AGENTS.md)'s status table and entries — this is the
   real record of what's been done, tested, and touched so far. Trust it
   over this table if the two ever disagree, and fix the disagreement.
3. Check the phase table for the earliest `Not Started` or `In Progress`
   step whose dependencies are all `Done`.
4. Open that step's file. Read it fully before writing any code — the
   "Open risks / assumptions" section may tell you something needs a fresh
   source-code check before you trust it.
5. Do the substeps in order. Update the status and progress log as you go.
6. When done, verify against the Definition of Done checklist literally,
   not from memory of having "basically done it."
7. Update this file's phase table row **and** append an entry to
   [AGENTS.md](AGENTS.md) for the step (files touched, tests run, status),
   then move to the next unblocked step. AGENTS.md is mandatory, not
   optional — see its own Rules section.
