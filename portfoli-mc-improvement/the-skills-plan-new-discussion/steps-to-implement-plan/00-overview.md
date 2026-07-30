---
name: 00-overview
status: living-document
purpose: entry point for any agent picking up this plan cold
---

# Portfolio-MC-Improvement — Implementation Plan Overview

**If you are an agent reading this for the first time: start here, then check
[AGENTS.md](AGENTS.md) for the real current state (this table can drift out
of date — AGENTS.md's entries are the evidence), then open the step file for
whatever you're about to work on. Each step file is written to stand on its
own — you should not need the full discussion transcript
(`the-sills-and-agentic-plan-discussion.md`) to understand what to do, only
to understand *how we got here* if you're curious.**

## The three aims (why this project exists)

1. **Focus 1 — Parameter sweep.** Given a strategy with known indicators,
   adaptively search its numeric parameter space (coarse pass → judge
   sensitivity → widen if flat, narrow if peaked → repeat, governed by an
   expectancy check, not a fixed grid) to reduce drawdown and raise Sharpe,
   converging on settings that pass real statistical validation.
2. **Focus 2 — Agent actually uses what already exists.** The 11 analysis
   angles, hypothesis evidence, judgment history — all computed and stored
   already, in real running services. The agent needs to read them back and
   let them drive decisions. Nothing new needs computing here.
3. **Focus 3 — Progressive daily portfolio.** Regime-aware, probability
   weighted daily allocation (which tickers + what cash ratio) that improves
   from yesterday's outcomes. The operational safety net around this
   (circuit breakers, drawdown scheduler) already exists; the allocation
   *intelligence* itself does not.

## The operating principle (how we build this)

**Skills are a knowledge library, not scripts.** We do not write procedures
for the agent to mechanically execute. At runtime the agent composes four
things itself:

- **Knowledge** — skills: what exists, what it means, what tends to matter.
- **Tools** — the existing `vinu-*` services, called through `vinu-agent`'s
  tool layer.
- **Memory** — existing stores (`HypothesisRegistry`, `ResearchStorage`,
  `judgment_store`, checkpoints). We do not rebuild these.
- **Governor** — a hard resource limit, a "is progress still happening"
  heuristic, and an "is continuing still worth it" expectancy heuristic,
  working together, not one flat rule.

Self-agency comes from the agent freely combining these four at runtime, not
from a script we hand it. Every step below either strengthens one of these
four ingredients or removes a reason the agent can't reach one of them yet.

## The core discovery this plan is built on

We did a deep, direct-source-read audit of `vinu-research`, `vinu-simulator`,
`vinu-strategy`, `vinu-portfolio`, `vinu-initial-analysis`, `vinu-tools`, and
`vinu-agent` before writing any of this. Finding, stated plainly: **the
intelligence layer is mostly already built, in real running code.** Backtest
statistical validation, overfitting checks, hypothesis/evidence tracking,
checkpointing, per-symbol exhaustion budgets, angle computation, circuit
breakers — all real, all already there. We grepped every existing skill file
for references to any of it: almost nothing. **The actual, confirmed gap is
narrower than "build an agentic system" — it's "the agent can't see or reach
most of what already exists."** This plan is shaped around closing that
specific gap first, then building the genuinely-missing pieces on top of a
foundation the agent can actually use.

Full evidence trail for this claim lives in `the-sills-and-agentic-plan-discussion.md`
if you want to verify any specific claim by re-reading the source yourself —
you should, if you're about to build on a claim you're unsure of. Re-verifying
a claim by reading the actual file beats trusting this document, always.

## The phase map

| Phase | Step file | Code | Depends on | Unlocks | Status |
|---|---|---|---|---|---|
| 0 | [01-verification-pass.md](01-verification-pass.md) | V0 | nothing | 03, 08, 09 (removes risk) | Done |
| 1 | [02-tool-wiring.md](02-tool-wiring.md) | A2 | nothing | 03, 08 | Done |
| 2 | [03-gatekeepers-skill.md](03-gatekeepers-skill.md) | B1 | 01, 02 | 07 | Done |
| 2 | [04-strategy-tag-layer.md](04-strategy-tag-layer.md) | B2 | nothing | 07 (alignment matching) | Done |
| 2 | [05-tool-catalog.md](05-tool-catalog.md) | B3 | nothing | general agent grounding | Done |
| 3 | [06-parameter-sweep-engine.md](06-parameter-sweep-engine.md) | A1 | nothing (independent build) | 07 | Done |
| 3 | [07-optimizer-rules-skill.md](07-optimizer-rules-skill.md) | B4 | 03, 06 | Focus 1 complete | Done |
| 3 | [08-governor.md](08-governor.md) | B6 | 01, 02 | 07 (paired design) | Done |
| 4 | [09-live-safety-doc.md](09-live-safety-doc.md) | B5 | 01 | Focus 3 safety story | Done |
| 5 | [10-focus3-portfolio-intelligence.md](10-focus3-portfolio-intelligence.md) | A3 | nothing (separate track) | Focus 3 complete | In Progress |

**Reading the table:** Phase 2's three steps run in parallel with each other.
Phase 3's `06` can start any time (it's an independent build), but `07`
needs both `03` and `06` finished first — it's the step that ties the sweep
engine to the evaluation skill. `08` is paired with `07`: design them
together even though they're separate files, because a governor designed
without knowing the optimizer's shape (or vice versa) tends to not fit.
Phase 5 (`10`, Focus 3) does not block or get blocked by anything else in
this table — it is deliberately a separate track, tackle it whenever, in
parallel with everything else if you have the capacity.

## Status legend

Update the `status` field in each step file's frontmatter as work happens:
- `Not Started` — nothing done yet.
- `In Progress` — actively being worked, note what's left in the file's own
  progress log section.
- `Blocked` — say what it's blocked on, and by which step.
- `Done` — deliverable exists and the Definition of Done checklist is
  fully checked. Update this overview's table row too when a step flips
  to Done, so this file stays the fast-scan source of truth for "where are
  we."

## How to use this folder if you are picking this up cold

1. Read this file fully.
2. Read [AGENTS.md](AGENTS.md)'s status table and entries — this is the
   real record of what's been done, tested, and touched so far. Trust it
   over this table if the two ever disagree, and fix the disagreement.
3. Check the phase table for the earliest `Not Started` or `In Progress`
   step whose dependencies are all `Done`.
4. Open that step's file. Read it fully before writing any code — the
   "Open risks / assumptions" section may tell you something needs a fresh
   source-code check before you trust it, especially anything inherited
   from Step 01.
5. Do the substeps in order. Update the status and progress log as you go.
6. When done, verify against the Definition of Done checklist literally,
   not from memory of having "basically done it."
7. Update this file's phase table row **and** append an entry to
   [AGENTS.md](AGENTS.md) for the step (files touched, tests run, status),
   then move to the next unblocked step. AGENTS.md is mandatory, not
   optional — see its own Rules section.
