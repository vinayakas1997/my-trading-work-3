---
name: doc-reality-fixes
closes: shortcoming #6 in ../01-vinu-components-shortcomings.md
status: done — both inaccuracies corrected with the real mechanism/caller, and 00-full-initial-explanation.md re-synced against actual code after tasks 01-08 landed
---

# Task: fix two plan docs that understate/misstate what's actually built

## Goal

Correct two specific inaccuracies found in `New-talk-agents/new-restructure/phases/` during the code
audit, and re-sync `00-full-initial-explanation.md`'s status markers once tasks 1-8 in this plan land.

## Why

Stale docs cost real time — the entire reason this implementation plan exists is that
`00-full-initial-explanation.md` described most of the pipeline as `proposed-not-built` when a direct
code audit found the opposite (TickerLedger, Thesis Intake, Significance Triage, cross-angle consensus,
sweep-engine wiring, and the kill switch are all real, wired, and tested). Don't let the same drift happen
to these plan docs.

## Current state (verified 2026-08-17)

Two specific, confirmed mismatches:

1. `New-talk-agents/new-restructure/phases/phase-1-sweep-engine-wiring/01-plan.md` describes explicit
   tool registration (a hardcoded list). The actual mechanism is
   `vinu-agent/vinu_agent/tools/__init__.py`'s automatic `BaseTool.__subclasses__()` discovery — any
   `BaseTool` subclass defined in the `tools/` package is auto-registered. Functionally correct outcome,
   but the doc will confuse anyone expecting to find an explicit registration list that doesn't exist.
2. `New-talk-agents/new-restructure/phases/phase-3-kill-switch/01-plan.md` (or its `04-implement-test.md`
   — locate the exact file) states `rebalance_guard` has "no real caller yet." This is false:
   `capital_allocator_hook.py` already calls `check_rebalance_allowed` for unwind requests. The doc
   understates what's actually built.

## Steps

1. Locate the exact line(s) in each cited plan doc making the inaccurate claim.
2. Fix wording in place — for #1, describe the auto-discovery mechanism instead of an explicit list; for
   #2, correct the "no real caller yet" claim to reflect that `capital_allocator_hook.py` does call it,
   and narrow the description to the actual remaining gap (the cross-process durability issue closed by
   task 04 in this plan).
3. Once tasks 01-08 in this implementation plan have landed, do a fresh pass over
   `New-talk-agents/new-restructure/mermaid-explanation.md` (the original, now also copied to
   `new-vision/00-full-initial-explanation.md`) and update its `status:` frontmatter and any
   `proposed-not-built`/`built, unused`/"no real trigger" language that this plan's work has since made
   stale. Don't do this until the other tasks actually land — updating it now would just recreate the
   same drift problem from the other direction.

## Acceptance criteria

- Both specific inaccuracies are corrected with the real mechanism/caller described in their place.
- After tasks 01-08 land, `00-full-initial-explanation.md`'s status language matches the real, current
  state of the codebase, verified the same way this plan was — by reading actual code, not by assuming
  the plan docs are right.

## Dependencies

Do last, after tasks 01-08. Fixing the docs before the underlying work lands just creates a new
temporarily-stale doc.
