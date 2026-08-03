---
name: start-here
status: index
purpose: entry point for any agent (or person) picking up the "agent consciousness" work cold. Read this first, then follow the pointers — do not re-derive the analysis below from scratch, and do not re-run the 1-month replay before reading testing-status/README.md.
---

# Start Here — Agent Consciousness / Discipline Work

## The one-paragraph version

`vinu-agent` (the LLM trading agent in `vinu-components`) was put through a
real 20-day simulated trading replay. The infrastructure worked. The
agent's own behavior didn't: it opened one position, then went silent —
zero tool calls — for 16 of the remaining 17 days, repeating stale numbers
from memory, and at one point **fabricated a stock price it never fetched
and repeated it confidently for 13 straight days.** That is not a minor
bug. It means the agent currently has no mechanism forcing it to verify
reality before acting, no way to tell a freshly-checked fact from a
half-remembered one, and no structured memory of its own past decisions to
learn from. This folder is the analysis of exactly what's missing and what
a working fix looks like — **nothing described in these files has been
implemented yet.** They are audits and design references, not a changelog.

## Read in this order

1. **`01-quant-agent-qualities.md`** — the framework, independent of this
   codebase: what data, "consciousness" (discipline/harness), and skills a
   real quant-trading agent needs, and why they depend on each other in
   that order (data grounds consciousness, consciousness governs skills).
2. **`02-vinu-components-where-how.md`** — that framework mapped onto the
   real `vinu-components` codebase, file paths and line numbers, honestly
   tagged ✅ exists-and-used / ⚠️ built-but-dormant / ❌ missing. **This is
   the source of truth for "what's actually true of our codebase today."**
   Keep it that way — when something below actually gets implemented,
   update *this* file's status tag and citation, don't just leave the fix
   sitting in file 03.
3. **`03-advanced-patterns-from-reference-repos.md`** — working answers for
   most of 02's gaps, found by reading real code in
   `personal-important/other-reference-repos/` (mainly `Vibe-Trading`, plus
   one reusable schema from `ref-fincept-terminal`). Cross-linked with 02
   in both directions — each gap row in 02 that has an answer here says
   "→ see 03."
4. **`01-plan-and-implementations/AGENTS.md`** — the actual build plan, one
   file per item, turning 03's four highest-priority patterns into concrete
   `vinu-components` file targets. Still `status: not-started` everywhere
   — this is a plan, not a changelog. When an item actually gets built,
   update its status here, in `01-plan-and-implementations/AGENTS.md`, and
   in `02`'s gap table — all three, not just one.

## Where the underlying evidence lives (don't re-run this)

- `02-the-1-month-back-testing/` — the actual replay run, results, and bug
  logs that this whole analysis is grounded in. `testing-status/README.md`
  has the current state of all 5 infra items. The specific run analyzed is
  `results/run-2026-07-06-2026-07-31-v2/` (`report.md`, plus raw
  `thinking.json`/`response.json`/`account_snapshot.json` per day).
- `the-project-vision/the-premarket-agents-answers-from-replay.md` — the
  evidence-cited behavioral rubric answers pulled from that same replay
  (this is where the fabricated-JNJ-price finding is documented in full,
  with the exact quote and day it first appeared).
- **Do not re-run the 20-day replay to "check" any of this again** unless
  you're specifically testing a new fix — it's expensive (real LLM calls,
  ~10 minutes minimum) and the existing run already has everything needed
  to evaluate the current state. If you do re-run it, follow the
  resumable/run-id convention in
  `02-the-1-month-back-testing/testing-status/day-stepper-replay-harness/test-log.md`.

## What NOT to do

- Don't treat any status in `02` as current without checking the file was
  actually updated after an implementation — a stale ✅/❌ tag is worse
  than no tag.
- Don't propose new "skills" (more tools, more analysis angles) as the fix
  for the replay's failure — the skills layer already has more real
  infrastructure (`generate_trade_plan` with real invalidation rules,
  bracket orders, portfolio-aware sizing) than the replay ever exercised.
  The gap is entirely in the consciousness layer; read `01`'s closing line
  again if this feels counterintuitive.
- Don't clone or vendor the reference repos wholesale — `03` documents
  specific patterns to reimplement, not dependencies to import.

## Current status as of this writing

Nothing in this folder has been implemented in `vinu-components` yet. The
priority order for what to build next is now a real plan, not just a
recommendation list: `01-plan-and-implementations/AGENTS.md` and its four
per-item files (fact-verification audit, forced ground-truth injection,
structured decision journal, audit-log schema), in that build order. The
one thing confirmed **not solved anywhere** — including in all six
reference repos — is a hard mechanism for the agent to genuinely defer or
say "not enough information" instead of always producing a plausible
answer. That stays open, and is explicitly excluded from the current plan
(see `01-plan-and-implementations/AGENTS.md`'s "not a plan item" note).
