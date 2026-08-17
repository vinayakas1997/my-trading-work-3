---
name: phase-3-test
status: proposed-not-built
purpose: concrete input/expected-output cases proving the Kill Switch actually blocks funding and rebalance requests, fails toward the safe direction, and doesn't stop monitoring during a halt.
---

# Phase 3 -- Test plan

**`test_mark_active_blocked_when_globally_halted`**
Input: `/broker/status` (mocked) returns `halted=True`, `scope=None`; a
`PEND` candidate is due for funding this cadence run.
Expected: the candidate transitions to `PENDBLOCK`, not `ACTIVE`;
`mark_active` is not called.

**`test_mark_active_proceeds_when_not_halted`**
Input: `/broker/status` returns `halted=False`.
Expected: funding proceeds normally to `ACTIVE`, same as Phase 2's tests.

**`test_scoped_halt_blocks_only_matching_scope`**
Input: halt engaged with `scope="AAPL"`; the cadence batch contains one
`AAPL` candidate and one `MSFT` candidate.
Expected: the `AAPL` candidate goes to `PENDBLOCK`; the `MSFT` candidate
funds normally -- proves scope narrowing actually narrows, not a global
block disguised as scoped.

**`test_broker_status_unreachable_defaults_to_halted`**
Input: the call to `/broker/status` raises/times out.
Expected: treated as halted -- no candidate in this cadence run reaches
`ACTIVE`, all affected candidates go to `PENDBLOCK` or remain `PEND`.
This is the fail-closed-toward-safety test and must not be skipped or
weakened -- it's the one check in this whole plan where the wrong
default has real financial consequence.

**`test_pendblock_transition_writes_ticker_ledger_row`**
Input: a candidate transitions to `PENDBLOCK`.
Expected: a `TickerLedger` row records it, distinct in `event_type` from
an ordinary `PEND` transition.

**`test_pendblock_auto_retries_after_resume_no_manual_action`**
Input: a `PENDBLOCK` artifact exists; the Kill Switch is resumed
(`halted=False`) before the next cadence run; no other action is taken.
Expected: the next cadence run automatically re-attempts funding for that
artifact and, if still otherwise eligible, transitions it to `ACTIVE` --
proves no separate "unstick" step is required.

**`test_rebalance_request_blocked_during_halt`**
Input: `capital_allocator`'s rebalancer attempts to send Monitor a
rebalance request while `halted=True` (global or matching scope).
Expected: the request is not sent / is rejected before reaching Monitor.

**`test_monitor_hold_decay_continues_during_halt`**
Input: `halted=True`; Monitor runs its ordinary periodic comparison of a
live position against its shadow twin.
Expected: the comparison and any hold/decay judgment still execute
normally -- only the *request* path to change a position is gated, not
Monitor's read-only monitoring.

**`test_scope_string_convention_matches_between_halt_and_status_check`**
Input: a halt issued with `scope=<artifact_id>`; a status check performed
with the same `artifact_id` value.
Expected: the check correctly reports halted for that scope -- this test
exists specifically to catch a convention mismatch (e.g. one side using
ticker symbol, the other using `artifact_id`) that would otherwise let a
scoped halt silently fail to block anything.

## End-to-end

**`test_phase3_halt_resume_walkthrough`**
Input: a `PEND` candidate approaches a cadence run -> halt engages
(scoped to its symbol) before that run -> cadence run executes -> halt
resumes -> next cadence run executes.
Expected, in order: first cadence run produces `PENDBLOCK`, not `ACTIVE`,
with a `TickerLedger` row; second cadence run (post-resume) automatically
funds it to `ACTIVE`, with its own `TickerLedger` row -- proves the full
block-then-auto-recover cycle works end to end, not just each half in
isolation.
