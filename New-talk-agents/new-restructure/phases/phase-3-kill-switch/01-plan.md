---
name: phase-3-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 3 -- turning the deferred Kill Switch stub into a live gate on funding and the rebalance-request path, small and mechanical, layered directly onto Phase 2's new PEND state.
---

# Phase 3 -- Kill Switch, for real

## What exists today, confirmed real

- `vinu_agent/broker/kill_switch.py` -- a deferred stub: `halt_trading`,
  `is_trading_halted`, `resume_trading`.
- HTTP front door in `vinu_agent/server/routes_broker.py`: `POST
  /broker/halt`, `POST /broker/resume`, `GET /broker/status`. Deliberately
  HTTP, not file-based -- every vinu-* service runs in its own container
  with a **private** tmpfs, so a file-based flag is only ever visible
  inside the one container that touched it (stated directly in that
  file's own module docstring). Any service that needs to halt trading --
  `vinu-portfolio`'s drawdown monitor, a human, a future automated check
  -- goes through this endpoint, not a local file.
- Both `HaltRequest` and `ResumeRequest` carry an optional `scope` field
  -- the kill switch already supports halting narrower than "everything"
  (e.g. one symbol or one strategy), not just a single global on/off.

## What Phase 3 adds

**1. `capital_allocator` checks `/broker/status` before `mark_active`.**
Immediately before funding a `PEND` candidate (right alongside the
staleness re-check from Phase 2 -- same moment, same reason: the picture
can move between approval and funding), check whether the Kill Switch is
engaged for the relevant scope. If engaged, the artifact goes to a new
holding state instead of `ACTIVE`.

**2. New state: `PENDBLOCK` ("funded, blocked by Kill Switch").** Storage
must never claim an artifact is `ACTIVE` (genuinely live) when the Kill
Switch is actually preventing it from executing -- `Monitor`'s later
shadow comparisons and the next allocation cycle's ranking both assume
`ACTIVE` means real deployed capital. `PENDBLOCK` keeps that assumption
true: funding was decided, but execution is held.

**3. The rebalancer's request path is gated too, by default.** Kill
Switch also blocks the rebalance-request path to Monitor, not just new
`mark_active` calls -- halting all order-flow-adjacent actions by
default, not only new funding. This was a deliberate design choice
(stated in `mermaid-explanation.md`'s Deeper structural fixes): two
defensible answers exist (block everything vs. let risk-reducing closes
through even during a halt), and this design picks the safer default
explicitly. Allowing de-risking closes through during a halt is a future,
deliberate override someone could add -- not the Phase 3 starting
behavior.

**4. Confirm, don't assume, what already checks the Kill Switch on the
live-execution side.** `routes_broker.py`'s own docstring says "OrderGuard
checks the kill switch from inside agent-api" (`vinu_agent/broker/
order_guard.py`, real, already used elsewhere this session). What's not
confirmed this session: whether `vinu-live`'s own order-placing path
(`breaker/engine.py`, `execution.py`) independently checks
`/broker/status` before placing a real order, or whether it relies
entirely on artifacts already being blocked upstream (i.e. never reaching
`ACTIVE` in the first place because of item 1-3 above). **Read
`vinu-live`'s `breaker/engine.py` directly before implementing this
phase** -- if it does *not* check the Kill Switch independently, that's a
real gap this phase must close (a strategy already `ACTIVE` before a halt
engages could keep trading in `vinu-live` even though `capital_allocator`
would now correctly block anything *new*), not something safe to assume
is already covered.
