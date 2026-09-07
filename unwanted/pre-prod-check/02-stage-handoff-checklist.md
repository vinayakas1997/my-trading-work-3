---
name: stage-handoff-checklist
status: planning only — not yet implemented
---

# Task: define what "pass" means at each stage

## Goal

A fixed, written-down checklist per pipeline stage — not just "did it
run" but "did it hand off the right thing to the next stage." This is
the vocabulary the manifest's `stage` column uses and the thing the
harness (task 03) actually evaluates.

## Why

"Did stage N run" is a weak check — the real risk in a multi-agent
pipeline is stage N producing something stage N+1 silently
misinterprets or never reads at all. Per the project owner's own framing:
for each ticker, check "did it execute, did it log properly, was that
step's data properly handed off to the next block" — not just a pass/fail
on the stage in isolation.

## The stage vocabulary

Use these exact strings as the `stage` value in the manifest — one row
per ticker per stage per test run:

| stage id | corresponds to | pass condition (execution) | pass condition (handoff) |
|---|---|---|---|
| `watchlist_gate` | change-gate ahead of Summary Agent | ticker correctly identified as changed/unchanged since last pass | if "changed," Summary Agent actually receives the trigger next cycle |
| `thesis_intake` (optional path) | Thesis Intake | theory checked against real evidence, verdict written | if "worth checking," Planner receives it identically to a system-generated idea |
| `summary_agent` | Summary Agent / `angle_synthesizer` | `get_all_angles(ticker)` called, summary + cross-angle consensus written to `TickerSummaryStore` | Planner's next triage pass actually reads this stored summary, not a stale one |
| `planner_triage` | Planner triage | fit tier + priority computed from the stored summary and existing artifact statuses (all non-terminal states checked) | `HypothesisRegistry` consulted before proposing; K-cap counter incremented correctly |
| `planner_idea` | `idea_generator` | recipe + parameter space chosen, tied to a specific angle characteristic | Researcher/Executor receives the recipe + reasoning intact |
| `sweep_execute` | Researcher/Executor role b | `run_parameter_sweep` completes, `completeness` field populated | ranked table + completeness reach role c's self-verdict step |
| `sweep_verdict` | Researcher/Executor role c | PASS/FAIL decided, incorporating PBO + walk-forward stability, completeness-gated | on FAIL, reasoning reaches the Planner loop-back; on PASS, the winning candidate reaches `risk_gatekeeper` |
| `risk_gatekeeper` | `risk_gatekeeper` | verdict computed via real `get_portfolio` data | APPROVED → artifact moves to "pending allocation" state; REJECTED → reaches Planner loop-back AND Significance Triage |
| `capital_allocator` | `capital_allocator` cadence run | batch ranked by `deflated_sharpe`, exposure re-checked, NEW-vs-NEW correlation checked, Kill Switch checked | funded → `mark_active` called and Live+Shadow actually picks it up; blocked-by-KillSwitch → correctly lands in the distinct "funded but blocked" state, never silently marked ACTIVE |
| `live_shadow` | Live+Shadow / `ShadowEvaluator` | paper twin running continuously off the same price feed | Monitor's periodic comparison actually reads current shadow state, not stale data |
| `monitor` | Monitor / `TradePlanOrchestrator` | hold/flag/suggest-drop decided each cycle | decay/drop correctly loops back to Planner via `HypothesisRegistry`; hold correctly leaves Live+Shadow running |
| `ticker_ledger_writes` | cross-cutting | every stage above wrote its expected row | rows are in chronological order, `ref_id` on each row resolves to a real record in the store it claims to point to (spot-check, not exhaustive) |
| `kill_switch_gate` | cross-cutting | engaging the Kill Switch mid-run actually blocks `mark_active` and the rebalance-request path | disengaging correctly resumes normal flow, no stuck state |
| `significance_triage` | cross-cutting | routine vs. unusual correctly classified for at least one deliberately-unusual scenario | delivery actually reaches the configured channel (only checkable once real Telegram/Discord credentials exist — see `../03-how-to-start.md`) |

## Steps

1. Confirm this stage list against the real code before the harness is
   built — file/function names above are taken from
   `../04-new-full-explanation.md` and may have drifted; re-verify each
   `pass condition` against the actual function/hook it describes.
2. For each stage, write the exact query or check that proves the
   "handoff" condition — not just "no exception was raised." E.g. for
   `summary_agent`, the check isn't "the function returned" — it's
   "querying `TickerSummaryStore` for this ticker now returns today's
   `run_id`."
3. Keep this table as the single source of truth for stage ids — task 03
   codes against these exact strings.

## Acceptance criteria

- Every stage in the pipeline (per `../04-new-full-explanation.md`) has
  exactly one row here — no stage silently skipped.
- Every "handoff" condition names a concrete, checkable fact (a specific
  table, column, or state value) — not a vague description.

## Dependencies

Depends on task 01 (the manifest needs this vocabulary for its `stage`
column, decided together in practice but written second here since the
schema doesn't need the specific stage names to be designed).
