---
name: phase-5-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving the extension points (HypothesisRegistry/TickerLedger writes, rebalance-request intake, shock trigger) work without ever compromising the orchestrator's existing, already-correct real-money logic.
---

# Phase 5 -- Test plan

**`test_closeout_writes_hypothesis_registry_evidence`**
Input: `feedback_loop.py`'s existing close-out path runs for a position
that decayed.
Expected: `HypothesisRegistry.add_evidence(...)` is called with the real
outcome and reason -- proves the missing write from `01-plan.md` item 1
is actually wired.

**`test_closeout_writes_ticker_ledger_row`**
Input: same close-out as above.
Expected: a `TickerLedger` row is written with `stage="monitor"` (or
equivalent) and the real close-out narrative -- not just the
`HypothesisRegistry` write in isolation.

**`test_audit_write_failure_does_not_block_or_reverse_the_close`**
Input: the real close-out executes successfully; the subsequent
`HypothesisRegistry`/`TickerLedger` write is simulated to fail.
Expected: the position close itself completed and is not rolled back or
reversed -- the audit-write failure is logged/queued for retry, and
critically, the test asserts the close already happened *before* the
audit write was attempted, proving the ordering guard rail, not just the
non-blocking behavior.

**`test_rebalance_request_can_be_declined_by_orchestrator`**
Input: a rebalance request arrives for position X ("unwind X to fund Y"),
but `TradePlanOrchestrator`'s own evaluation of X finds no invalidation
or contingency reason to act.
Expected: X remains open; the request is declined, not force-executed.

**`test_rebalance_request_folds_into_next_cycle_evaluation`**
Input: a rebalance request arrives mid-cycle.
Expected: it's incorporated into the orchestrator's own next evaluation
pass as an input signal -- it does not trigger an immediate, separate
close action that bypasses the orchestrator's normal decision path.

**`test_shock_trigger_fires_off_cycle_check`**
Input: a `shock_clustering` event fires for a symbol with an open
position, mid-way between two scheduled cycles.
Expected: an evaluation runs immediately (before the next scheduled
cycle would have), using the same logic as a normal cycle.

**`test_shock_trigger_debounced_within_window`**
Input: 5 shock events fire for the same symbol within a short window
(inside the debounce interval).
Expected: exactly one off-cycle check runs for that burst, not 5.

**`test_hard_invalidation_not_delayed_by_batching`** *(only if Phase 5
adds batching -- confirm via `01-plan.md` item 4's read of the real
orchestrator loop first)*
Input: one position breaches a hard invalidation condition while a
routine batch-review window for other positions is still open.
Expected: the breaching position is evaluated and acted on immediately,
not held until the batch window closes.

## End-to-end

**`test_phase5_decay_to_next_planner_pass_walkthrough`**
Input: a live position decays over several cycles and is closed by
`TradePlanOrchestrator`'s existing logic (unmodified).
Expected, in order: real close executes -> `HypothesisRegistry` and
`TickerLedger` both receive the outcome -> a simulated next Planner pass
on that same ticker, performing its required pre-proposal
`HypothesisRegistry` consult, sees the specific failure reason and does
not propose the same shape of idea unchanged. This is the case that
proves the memory loop this phase closes actually reaches the Planner,
not just that the writes happen in isolation.
