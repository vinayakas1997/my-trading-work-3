---
name: phase-5-guard-rail
status: proposed-not-built
purpose: what keeps the rebalance-request intake advisory (not a second authority), keeps shock-triggered checks from flooding, and keeps new audit writes from ever blocking a real trade decision.
---

# Phase 5 -- Guard rails

**The rebalance-request intake is advisory input, never a forced action --
this is the whole point, restate it precisely in the implementation.**
`TradePlanOrchestrator`'s existing invalidation/contingency logic keeps
final say. A rebalance request that conflicts with what the orchestrator's
own evaluation concludes (position is fine, no reason to unwind) can be
declined. If the request could force an action regardless of the
orchestrator's own judgment, this phase would have rebuilt the exact
two-authority bug it exists to avoid, just with extra steps.

**Real trade actions must never be blocked or reversed by a failed
`HypothesisRegistry`/`TickerLedger` write.** These are new dependencies
being added to a code path that already moves real money. The write-order
must be: execute the real action first (or let the orchestrator's
existing logic execute it, unmodified), *then* write the audit trail,
best-effort and retryable. If the audit write fails, log the failure and
retry later -- never roll back or gate the actual position close on it.
Audit-trail completeness is important; it is never allowed to outrank
order-execution correctness.

**Shock-triggered off-cycle checks need a debounce, or a genuinely
volatile period becomes a cost-runaway period.** If `shock_clustering`/
`shock_personality` fires repeatedly in a short window -- exactly the
scenario this trigger exists to react to quickly -- an un-debounced
trigger could fire the same off-cycle check many times back-to-back for
the same symbol. Rate-limit re-triggering per symbol to some minimum
interval, so the system stays responsive to the *first* shock signal
without re-running redundant checks on every subsequent one in the same
burst.

**If batching gets added (item 4 in `01-plan.md`), it must not delay a
genuinely urgent single-position event.** Batching is for routine,
periodic review across many quiet positions -- it must not become a
reason a hard invalidation trigger (one position blowing past a stop)
waits for a batch window to close before acting. Keep "must-act-now"
paths (hard invalidation, shock-triggered) explicitly outside whatever
batching logic gets added for routine checks.
