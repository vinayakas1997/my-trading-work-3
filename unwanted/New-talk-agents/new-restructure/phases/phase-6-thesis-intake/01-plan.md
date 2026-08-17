---
name: phase-6-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 6 -- the genuinely new second entry point. Unlike Phases 4/5, there's no existing code to fix here; this is real new build, using the real skills mechanism and HypothesisRegistry rather than inventing new storage.
---

# Phase 6 -- Thesis Intake

## What this phase builds

A second entry point, alongside the watchlist: a human hands the
pipeline a raw theory -- an idea or analogy, not code, not even a formal
recipe -- and it gets checked against real evidence before it's allowed
to consume any of the pipeline's downstream budget.

**Dependency note:** only depends on Phase 0 (`TickerLedger`) and the
real, already-built `HypothesisRegistry` -- does **not** require a
separate new Planner triage stage to exist first. Thesis Intake hands
cleared theories to whatever currently serves that role -- today, that's
the real `research` team's manager loop (Phase 1's upgrade target). If a
dedicated Planner triage stage gets built later, Thesis Intake's handoff
target just moves one hop upstream; nothing else about this phase
changes.

## The cost-control gate (`THGATE`), built first

Cheap, deterministic, no LLM call, ahead of Thesis Intake itself -- same
shape as Phase 0's change-gate, applied to a different question:

1. **Near-duplicate check** against `HypothesisRegistry` -- has a
   near-duplicate theory already been evaluated for this ticker recently?
2. **Shared K-cap check** -- is this ticker already at its per-cycle
   distinct-candidate budget?

**Where the K-cap counter actually lives:** not a separate counter
variable to keep in sync across two entry points -- derive it by querying
`TickerLedger` (Phase 0) for the count of distinct-candidate-proposed
events for this ticker so far this cycle, regardless of which entry point
(`watchlist` or `human`) produced each one. One source of truth, no
separate state to drift out of sync with the Planner's own count.

Only "no duplicate AND under budget" reaches Thesis Intake itself -- an
LLM call.

## Thesis Intake itself

**What it reads:** the human's stated theory, plus real evidence already
gathered for that ticker (`TickerLedger`, `HypothesisRegistry`, the
Summary Agent's stored read via `TickerSummaryStore`).

**What it references:** two reference documents via the real, already-
built skills mechanism (`vinu_agent/agent/skills.py`'s `SkillsLoader`,
`vinu_agent/tools/load_skill_tool.py`) -- a strategy-definitions doc (what
shapes of strategy exist to test a theory like this) and a risk-rules doc
(what would disqualify it outright).

**Refinement to the original mermaid-doc framing: two separate skill
*files*, not two sections of one file.** The original design described
"strategy-definitions" and "risk-rules" as two sections within one skill.
For the governance fix (skill-edit audit log, below) to actually detect
"an edit to the risk-rules content" as a distinct, loggable event, it
needs an unambiguous boundary -- a whole-file diff on
`skills/thesis-intake/risk-rules.md` is directly implementable; detecting
edits to one section inside a combined markdown file is not, without
building a section-aware diff tool this phase has no reason to build.
Two files, same directory (`skills/thesis-intake/strategy-definitions.md`,
`skills/thesis-intake/risk-rules.md`), same `load_skill` mechanism.

**What it writes:** no code, ever -- only reads, compares, and produces a
verdict ("worth checking" or "doesn't hold up, here's the contradicting
evidence"). Written into `HypothesisRegistry` tagged `source="human"` --
reuses the exact store and evidence-tracking pipeline already built, no
new "human theories" table.

**On a "worth checking" verdict:** hands off to the same downstream loop
any system-generated idea uses (see dependency note above) -- same loop,
different front door.

## The skill-edit audit log

New, ticker-agnostic (an edit to `risk-rules.md` isn't about one ticker).
Any commit/edit touching `skills/thesis-intake/risk-rules.md` gets logged
as a visible, reviewable event -- separate store from `TickerLedger` since
it's not ticker-keyed. Simplest real implementation: a file-system watch
or a pre-commit-style hook on that specific path, writing an entry with
who/when/diff-summary. Confirm the project's existing skill-loading code
(`skills.py`) doesn't already have a hook point for this before building
a separate watcher.
