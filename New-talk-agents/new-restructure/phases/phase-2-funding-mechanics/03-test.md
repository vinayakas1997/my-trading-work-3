---
name: phase-2-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving batched, vinu-portfolio-backed funding works and fails safely when the cross-service call doesn't.
---

# Phase 2 -- Test plan

**`test_approved_moves_to_pend_not_mark_active`**
Input: `risk_gatekeeper` returns `APPROVED` for a candidate.
Expected: the artifact's status becomes `PEND`; `mark_active` is **not**
called as part of this verdict -- assert on the actual status value and
that the `mark_active` call count is zero at this point.

**`test_capital_allocator_batches_pend_since_last_cadence`**
Input: 3 artifacts transition to `PEND` between two consecutive cadence
runs.
Expected: the next cadence run ranks all 3 together in one pass, not
one-at-a-time as each arrived.

**`test_funding_uses_vinu_portfolio_weights_not_fixed_fraction`**
Input: a `PEND` batch; `vinu-portfolio`'s allocation endpoint (mocked)
returns specific, non-uniform weights per candidate.
Expected: funded sizes match the returned weights -- not the old
fixed-fraction-of-budget rule.

**`test_funding_never_exceeds_gatekeeper_approved_size`**
Input: `vinu-portfolio` (mocked) returns a weight *larger* than what
`risk_gatekeeper` originally approved for that candidate.
Expected: funded amount is capped at the originally-approved size, proving
the portfolio engine can only shrink, never expand, an existing approval.

**`test_funding_uses_smaller_size_when_portfolio_computes_less`**
Input: `vinu-portfolio` (mocked) returns a weight *smaller* than the
approved size.
Expected: funded at the smaller, portfolio-computed size.

**`test_vinu_portfolio_unreachable_skips_funding_this_cycle`**
Input: the call to `vinu-portfolio`'s allocation endpoint raises/times out.
Expected: zero artifacts funded this cadence run; the `PEND` batch is
retained unchanged for the next attempt; a distinct failure event is
logged (not indistinguishable from "batch was empty").

**`test_pend_transition_and_skip_events_write_ticker_ledger_rows`**
Input: one `PEND` transition, one skipped-cadence-due-to-unreachable-
portfolio event.
Expected: both produce a `TickerLedger` row with the correct `stage`/
`event_type` -- proves the "growing invisible queue" guard rail is
actually wired, not just documented.

**`test_cadence_boundary_edge_case_included_exactly_once`**
Input: an artifact transitions to `PEND` at the exact timestamp a cadence
run begins.
Expected: it appears in exactly one cadence run's batch -- not omitted
from both (silently skipped) and not double-counted in two consecutive
runs.

**`test_new_vs_new_correlation_reduces_or_excludes_within_batch`**
Input: two `PEND` candidates, each individually fine against the existing
book, but highly correlated with each other (simulated via
`vinu-portfolio`'s mocked correlation-aware response).
Expected: the funded outcome reflects that collective correlation --
e.g. one is funded at reduced size or excluded -- not both funded at full
individually-approved size as if the check never happened.

## End-to-end

**`test_phase2_full_batch_cycle`**
Input: a realistic batch of 4 `PEND` candidates assembled over two
cadence intervals, real (not mocked) `SqliteStrategyStore` status
transitions, `vinu-portfolio` call mocked to return a real-shaped
response including a correlation matrix.
Expected, in order: staleness re-check runs immediately before funding
-> `vinu-portfolio` is called once with the whole batch (not once per
candidate) -> funded sizes respect both the per-candidate cap and the
batch-collective correlation result -> every funding/skip decision writes
a `TickerLedger` row -> artifacts that got funded transition to `ACTIVE`
via `mark_active`, artifacts that didn't remain `PEND` for the next cycle.
