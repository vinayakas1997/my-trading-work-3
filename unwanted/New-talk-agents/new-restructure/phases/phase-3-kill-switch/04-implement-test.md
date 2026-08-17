---
name: phase-3-implement-test
status: built -- Phase 3 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 3 -- Implementation record

Built 2026-08-11, directly following Phase 2 in the same session.

## What direct code reading found (the plan's own required step 4)

- **`OrderGuard.check()` called `is_trading_halted()` with no scope at
  all** -- a symbol-scoped halt never actually blocked anything at the
  real order-execution boundary, only a global halt worked. This is the
  actual, confirmed gap: not that scoped halts didn't exist (they did,
  fully built in `kill_switch.py`/`routes_broker.py`), but that the one
  real enforcement point never passed the scope through. Fixed:
  `is_trading_halted(scope=symbol)`, one line, `symbol` was already a
  parameter `check()` had on hand.
- **vinu-live does NOT bypass the kill switch.** Read `breaker/engine.py`
  and `trade_plan/orchestrator.py`/`scheduler.py` directly: `breaker/
  engine.py`'s `state.halted` is vinu-live's own, separate circuit
  breaker (drawdown-triggered), unrelated to vinu-agent's kill switch.
  But every REAL order vinu-live places goes through `{agent_api_url}/
  agent/broker/order` -- the exact same guarded endpoint
  (`routes_broker.py` -> `TradeTool` -> `OrderGuard.check()`) the LLM's
  own `submit_order` tool uses. So the `OrderGuard` scope fix above
  protects both call paths at once; no separate kill-switch check needed
  inside vinu-live itself.
- **`GET /agent/broker/performance/{artifact_id}` already exists and is
  implemented** (`routes_broker.py`, backed by `broker/performance_
  store.py`) -- contradicts an earlier finding from before this build
  session that it 404s. Flagged here rather than silently trusted or
  silently corrected without saying so; Phase 4 should re-verify this
  itself when it's actually built, not inherit this note secondhand.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-agent/vinu_agent/broker/order_guard.py` | modified | `is_trading_halted()` -> `is_trading_halted(scope=symbol)` -- the real scope-convention fix. |
| `vinu-components/vinu-agent/tests/test_order_guard.py` | modified | New `TestKillSwitchScope` (3 tests): global halt, no halt, scoped halt checked with the real symbol. |
| `vinu-components/vinu-research/vinu_research/models.py` | modified | `ArtifactStatus.PENDBLOCK` added. |
| `vinu-components/vinu-research/vinu_research/storage/strategy_store.py` | modified | `_ALLOWED_TRANSITIONS`: `PEND<->PENDBLOCK`, both `->ACTIVE`/`DISABLED`. New `mark_pendblock()` (preserves `approved_size`). |
| `vinu-components/vinu-research/tests/test_strategy_store_transitions.py` | modified | 5 new tests: PEND->PENDBLOCK preserves approved_size, PENDBLOCK->PEND, PENDBLOCK->ACTIVE on retry, PENDBLOCK->DISABLED, BENCHING->PENDBLOCK correctly rejected. |
| `vinu-components/vinu-agent/vinu_agent/agent/capital_allocator_hook.py` | modified | New `_is_halted(scope)` (fail-closed to halted on any error, in-process call to `kill_switch.py`, no self-referential HTTP). Funding loop now re-fetches the artifact, checks the kill switch for its symbol immediately before `mark_active`, and calls `mark_pendblock()` instead if engaged -- with its own distinct `TickerLedger` event (`event_type="PENDBLOCK"`, never confused with `"funded"`). |
| `vinu-components/vinu-agent/tests/test_capital_allocator_hook.py` | new | 7 direct tests against `apply_capital_allocator_decision` -- global halt, no halt, scoped halt blocks only the matching scope, unreachable-check fails closed, distinct TickerLedger event, auto-retry after resume (no manual action), not-funded candidates never reach the kill-switch check at all. |
| `vinu-components/vinu-agent/vinu_agent/agent/rebalance_guard.py` | new | `check_rebalance_allowed(scope) -> bool` -- standalone, ready-to-call gate for Phase 5's not-yet-built rebalancer. Fail-closed to blocked. |
| `vinu-components/vinu-agent/tests/test_rebalance_guard.py` | new | 4 tests covering the same fail-closed direction and scope pass-through. |

## Design deviations from `01-plan.md`, and why

- **No new code was added inside vinu-live.** The plan's item 4 explicitly
  required confirming whether vinu-live independently checks the kill
  switch before assuming a gap existed there. It doesn't need to --
  confirmed by reading `orchestrator.py`/`scheduler.py` directly, every
  real order already routes through the one guarded endpoint the
  `OrderGuard` fix above covers. Building a second, redundant check inside
  vinu-live would have been unnecessary surface, not extra safety.
- **The kill-switch check for funding lives in `capital_allocator_hook.py`,
  not inside `ComputeAllocationCandidatesTool`.** The guard rail is
  explicit that the check should happen "immediately before the funding
  call, not earlier in the cadence run" -- the hook is the one place that
  actually calls `mark_active`, so that's where the check belongs, not
  duplicated into the (read-only, `is_readonly=True`) compute tool a
  cadence run earlier.
- **The rebalance-request gate (`rebalance_guard.py`) is a standalone
  function with no real caller yet**, not integrated into a live
  rebalancer -- because no rebalancer/Monitor exists in code yet (Phase
  5's own plan says so explicitly: "capital_allocator's rebalancer needs
  an actual target to call -- confirmed nowhere yet that one exists").
  Built and fully tested now so Phase 5 has an already-correct,
  already-tested gate to import rather than needing to re-derive the
  fail-closed direction under time pressure later. `test_rebalance_
  request_blocked_during_halt` and `test_monitor_hold_decay_continues_
  during_halt` from `03-test.md` are not yet meaningfully testable
  against real code for the same reason -- deferred to Phase 5, not
  skipped silently (recorded here, not just omitted).

## Test results

```
vinu-agent:      498 -> 512 passed (full suite; 3 + 7 + 4 = 14 new tests)
vinu-research:   580 -> 585 passed, 1 skipped (full suite; 5 new PENDBLOCK-transition tests)
```

No regressions in either package's full suite.

## Known follow-ups (not blocking, not silently dropped)

- ~~The check-then-act race window is real, accepted, not closed~~ --
  **closed 2026-08-11.** `broker/kill_switch.py` now exposes
  `kill_switch_lock()`, a real OS-level file lock (`fcntl.flock` on
  POSIX, `msvcrt.locking` on Windows) that `halt_trading()`/
  `resume_trading()` acquire, and that `capital_allocator_hook.py`'s
  check-then-mark_active section and `trade_tool.py`'s
  pre_approve-then-submit_order section now also acquire around their
  own critical sections. A halt can no longer land in the gap between a
  check and the action it gates -- genuinely mutually exclusive, not
  just a narrowed window. Found and fixed alongside this: `trade_tool.py`
  was silently discarding `guard.pre_approve()`'s result entirely (a
  halt engaged between the two checks would correctly report
  not-allowed, but the order was submitted anyway, no lock needed to
  trigger that one) -- now checked and rejected like the initial
  `guard.check()`. Full record: `New-talk-agents/new-thinking/
  new-restructure/kill-switch-race-fix-implement-test.md`. vinu-agent:
  650 -> 659 passed, no regressions.
- **Phase 5 must actually wire `check_rebalance_allowed()` into the real
  rebalancer once it exists**, and confirm Monitor's read-only hold/decay
  path never calls it (by construction today it can't -- nothing calls
  this function yet at all).
- **`/agent/broker/performance/{artifact_id}` being already-implemented**
  (found above) should be re-confirmed, not re-assumed, when Phase 4
  actually starts -- read the real `broker/performance_store.py` schema
  at that time rather than trusting this note.
