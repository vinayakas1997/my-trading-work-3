---
name: stale-test-counts-in-e2e-agents
status: fixed
severity: documentation-staleness
---

# Bug: `end-to-end-test/AGENTS.md` cited pre-implementation test counts

## What was wrong

[`end-to-end-test/AGENTS.md`](../AGENTS.md)'s "What this folder does not
cover" section cited **"266 passing in `vinu-agent`, 489 in
`vinu-research`, 4 in `vinu-initial-analysis`"** as the reason this folder
doesn't re-verify the `implementation-plan-from-04` mechanisms
individually.

Those numbers don't match the actual final state, per the same
`implementation-plan-from-04` component `status.md` files this claim is
supposed to be summarizing:

- `vinu-agent`: [`implementation-plan-from-04/vinu-agent/status.md`](../../implementation-plan-from-04/vinu-agent/status.md)
  states **280 passed** ("was 224 before this work... +56 new tests"). 266
  doesn't match either the before-count (224) or the after-count (280) — it
  doesn't correspond to any documented checkpoint at all.
- `vinu-research`: [`implementation-plan-from-04/vinu-research/status.md`](../../implementation-plan-from-04/vinu-research/status.md)
  states **500 passed** ("was 489; +11 new tests"). 489 is exactly the
  *before* count, not the final one — this file was citing the baseline as
  if it were the result.
- `vinu-initial-analysis`: 4 was already correct and unchanged.

## Why it mattered

Lower severity than the approve-step bug (nothing breaks from a stale
number in a "why we don't re-test this" justification), but it's the kind
of thing that erodes trust in every other number in this project's docs —
if someone spot-checks this one against the component status files and
finds a mismatch, it casts doubt on numbers elsewhere that happen to be
correct. It's also a symptom worth naming: this file was evidently written
before Pieces 4–5 (freshness reader, research-digest reader) and the
`vinu-research` regime-recompute/digest work landed, and never got a pass
to reconcile against the final numbers.

## What was fixed

Updated [`end-to-end-test/AGENTS.md`](../AGENTS.md)'s "What this folder
does not cover" section: 266 → 280, 489 → 500, and added a citation
(`implementation-plan-from-04/*/status.md`) so the number has a traceable
source instead of being a bare, unverifiable figure.

## What was achieved

The one place in this folder that summarizes "how much is already tested
elsewhere" now actually matches the components it's summarizing, and
points at where to re-verify it if it drifts again.
