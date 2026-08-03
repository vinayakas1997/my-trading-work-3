---
name: research-run-missing-approve-step
status: fixed
severity: would-break-a-real-run
---

# Bug: `03`'s checklist never approves a research run, but assumed artifacts appear anyway

## What was wrong

[`03-strategy-research-and-simulation.md`](../03-strategy-research-and-simulation.md)
described `POST /research/run` as running the full **"generate → backtest →
promote"** pipeline in one call, and its verification step framed an empty
`/research/artifacts` list after a "completed" run as meaning *"the
pipeline ran but nothing passed promotion criteria"* — i.e. it treated
promotion as something the pipeline itself decides and does automatically.

This is not what the real code does. Confirmed directly in
`vinu-components/vinu-research/vinu_research/service.py`:

- `run_research()` (line 68) only ever constructs and persists a
  `ResearchRunRecord` with a status. It never touches `ArtifactStatus` or
  creates an `Artifact`.
- Artifact creation only happens in `approve_run()` (line 268) →
  `_create_artifact_from_run()` (line 312) — a **separate, explicit** call
  that nothing in the pipeline invokes on its own.

[`understanding-project/a-new-strategy-added.md`](../../understanding-project/a-new-strategy-added.md)
— written earlier by grepping this same code — already documented this
correctly: *"Promotion itself is always a manual call. Nothing in
`vinu-research` auto-approves a run,"* and named this exact mistake as
*"the one people skip, because step 1 already returns a `completed` status
that looks like the strategy is done."* `03` was never reconciled against
that finding. A `grep -i approve` across the whole
`04-agentic-still-refinement` folder, before this fix, only matched
`understanding-project` — the word never appeared in `02`/`03`/`04`/`05`.

## Why it mattered

This is the one bug in this folder that isn't just stale prose — it would
have produced a real, confusing failure. Following `03` exactly as written
(trigger `/research/run`, never call `/approve`) means
`/research/artifacts` comes back empty for a reason that has nothing to do
with promotion criteria. That empty result then cascades:

- `03` step 4 (simulate against "the artifact strategy name from step 3")
  has no artifact name to use.
- `04`'s entire premise — confirming `vinu-strategy`/`vinu-portfolio`
  actually reflect what `03` generated — has nothing to find, and would
  read as "aggregation is broken" when the real cause is upstream and has
  nothing to do with aggregation.
- `05`'s month-long agent replay has no promoted strategy to trade against
  at all.

All three downstream failures would look like real system bugs. The actual
cause would be a missing manual step in the test plan itself.

## What was fixed

In [`03-strategy-research-and-simulation.md`](../03-strategy-research-and-simulation.md):

1. Added an explicit warning in the file's intro section stating the
   approve step is mandatory and citing the code/doc evidence above.
2. Corrected step 2's description of `POST /research/run` — it runs
   generate → backtest → **validate**, and writes a `ResearchRunRecord`;
   it does not promote anything by itself.
3. Removed the incorrect "empty artifact list means nothing passed
   promotion criteria" claim from step 3 (that check no longer belongs
   there — promotion hasn't been attempted yet at that point).
4. Inserted a new **step 3a** — "Approve each run — the mandatory,
   easy-to-skip step" — with its own trigger (`POST
   /research/runs/{run_id}/approve`), verify (`GET /research/artifacts`),
   and document sub-sections, correctly distinguishing "empty because
   nothing's been approved yet" from "empty because it was approved and
   genuinely rejected/benched."
5. Updated every downstream reference (step 4's payload comment, the
   "Document" section, the final confirm-before-moving-on checklist) to
   point at step 3a instead of assuming promotion already happened by
   step 3.

## What was achieved

`03` now matches what the real `vinu-research` code actually does, and a
person or agent following it step by step will get a real promoted
artifact before `04` and `05` depend on one existing. The checklist can no
longer produce a false "aggregation gap" or "no strategy to replay against"
finding that's actually just a skipped manual call.
