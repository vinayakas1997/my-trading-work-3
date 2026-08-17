---
name: golden-path-and-edge-cases
status: planning only — not yet implemented, not yet run
---

# Task: the actual scenarios to run through the harness

## Goal

A concrete list of runs to execute with task 03's harness — not just the
happy path, since the happy path is the least likely place for a
multi-agent pipeline to actually break.

## Why

Per the project owner: go "deeper" than a chatbot status layer first —
verify each stage's handoff for real, including the branches that don't
show up unless something is deliberately pushed off the golden path
(a FAIL verdict, a REJECTED gate, the Kill Switch engaging mid-flight).
These are exactly the paths most likely to have a real bug, since they're
exercised least often in normal development.

## Scenarios

1. **Golden path, one ticker, no failures.** Watchlist → Summary Agent →
   Planner → sweep PASS → `risk_gatekeeper` APPROVED → funded → Live+Shadow
   → Monitor hold. Confirms the basic chain works end to end at all.

2. **Sweep self-verdict FAIL, then re-proposal.** Force (or find) a
   candidate that fails role c's verdict; confirm the reasoning actually
   reaches the Planner and the next proposal on that ticker reflects it
   (not just that a FAIL was logged, but that it changed the *next*
   proposal).

3. **`risk_gatekeeper` REJECTED.** Confirm the artifact stays in its
   prior state (not discarded), the reason reaches the Planner loop-back,
   AND Significance Triage receives it (per the coverage fix described in
   `../04-new-full-explanation.md`'s `risk_gatekeeper` section).

4. **Kill Switch engaged mid-flow.** Engage it after a candidate is
   APPROVED but before `capital_allocator`'s next cadence run. Confirm
   funding lands in the "funded but blocked" state, never silently
   ACTIVE, and that re-checking after disengaging correctly resumes
   without a stuck or duplicate state.

5. **Thesis Intake entry point, near-duplicate rejected.** Submit a
   theory, then a near-duplicate one immediately after. Confirm the
   second is discarded by the cheap check before reaching an LLM call —
   this specifically tests the cost-control path, not just the happy
   "worth checking" path.

6. **Thesis Intake entry point, shared K-cap enforced across both doors.**
   Push a ticker to its K-cap via the watchlist path, then submit a
   genuinely novel human theory for the same ticker in the same cycle.
   Confirm it's deferred by the *shared* counter, not accepted because
   Thesis Intake's own duplicate-check alone doesn't know about the
   watchlist path's usage.

7. **Rebalancer request vs. Monitor authority.** Trigger a rebalance
   REQUEST from `capital_allocator` targeting a position Monitor is
   independently evaluating that same cycle. Confirm there's no race —
   Monitor's authority over the actual close/hold decision is respected,
   the rebalancer never closes anything directly.

8. **Monitor decay → Planner → HypothesisRegistry loop.** Let a position
   decay to the point Monitor flags drop. Confirm the outcome is written
   to `HypothesisRegistry`, and that the *next* Planner pass on that
   ticker actually reads it before proposing again (not just that it was
   written somewhere).

9. **Multiple tickers in one `capital_allocator` batch.** At least two
   tickers reach "approved, pending allocation" in the same cadence
   window. Confirm the batch-collective correlation check runs across
   both, not just each independently against the existing book.

## Steps

1. Pick 2-3 real tickers with enough historical data behind them to
   plausibly hit scenarios 2, 3, and 8 without artificially forcing bad
   data (a ticker likely to trigger a real FAIL/REJECTED naturally is
   more informative than a synthetic one).
2. For scenarios that need to be *forced* (4, 5, 6, 7 — timing-dependent
   or requiring a deliberate trigger), decide per-scenario whether to
   inject the trigger via a test-only override or wait for a natural
   occurrence; document which approach was used in the manifest's `notes`
   field so results aren't mistaken for organic behavior later.
3. Run each scenario through task 03's harness under its own
   `test_run_id`, so results are queryable independently.
4. Record any scenario that can't be run without code changes (e.g. no
   existing way to force the Kill Switch mid-flow in a controlled test)
   as its own follow-up — that's itself a real gap worth knowing about,
   not just a blocked test.

## Acceptance criteria

- All 9 scenarios have a manifest entry (even if some end in documented
  `fail` — the goal is knowing, not a clean scorecard).
- Every scenario that fails has `notes` specific enough to turn directly
  into a bug report, not just "didn't work."

## Dependencies

Depends on task 03 (the harness). Task 02's checklist defines what "pass"
means within each scenario's individual stages.
