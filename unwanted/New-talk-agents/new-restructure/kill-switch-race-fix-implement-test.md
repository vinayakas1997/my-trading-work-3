---
name: kill-switch-race-fix-implement-test
status: built -- the check-then-act race window Phase 3's own record left "accepted, not closed" is now closed
purpose: record of what was actually touched and tested. Not a new phase -- a direct fix to a gap Phase 3's 04-implement-test.md explicitly named and left open, done when asked "why still open when you know the fix."
---

# Kill-switch check-then-act race -- implementation record

Built 2026-08-11. Phase 3's own implementation record said this plainly:
"The check-then-act race window is real, accepted, not closed... No
distributed lock was built; none was called for." Asked directly why it
was still open given the fix was already known, went and built it.

## The real race, confirmed by reading the code

`capital_allocator_hook.py::apply_capital_allocator_decision`: the
kill-switch check (`_is_halted(ticker)`) and the action it gates
(`strategy_store.mark_active(artifact_id)`) were two independent calls,
each atomic on its own, with nothing preventing `halt_trading()` from
completing in the gap between them. Same shape, separately confirmed by
reading `trade_tool.py`: `guard.check()` runs early, but the real order
submission (`broker.submit_order(...)`) happens later, after a
`require_confirmation` branch that can return early -- `guard.
pre_approve()` (a fresh re-check, including the kill switch) runs
immediately before submission specifically to close most of that gap.

**A second, unrelated bug found while reading this path closely:**
`pre_approve()`'s `GuardResult` was computed and then never checked --
`guard.pre_approve(symbol, side, qty)`'s return value was discarded, and
`broker.submit_order(...)` ran unconditionally right after it. A halt
engaged between the initial `guard.check()` and this point would
correctly report `not allowed` from `pre_approve()`, but the order went
through anyway. This wasn't a race/concurrency bug at all -- it would
misbehave every single time, on any machine, no timing required. Fixed
alongside the lock, not instead of it.

## What got built

- `broker/kill_switch.py`: `kill_switch_lock()`, a real OS-level advisory
  file lock (`fcntl.flock` on POSIX -- every real deployment, python:3.12
  -slim containers; `msvcrt.locking` as the Windows dev-environment
  fallback) at `/tmp/vinu-trading-halt.lock`. Deliberately an OS-level
  lock, not `threading.Lock()` -- `halt_trading()` can be called from a
  completely different process (vinu-portfolio's drawdown monitor via
  `/broker/halt`, a human operator, a future automated monitor), so an
  in-process-only lock would not have closed the actual gap.
  `halt_trading()`/`resume_trading()` now acquire this lock around their
  file writes.
- `agent/capital_allocator_hook.py`: the kill-switch check through
  `mark_active`/`mark_pendblock` (plus the TickerLedger write) is now
  wrapped in `kill_switch_lock()`. A halt can no longer land between the
  check and the transition it gates.
- `tools/trade_tool.py`: `guard.pre_approve()`'s result is now checked
  (rejects with the real reason if not allowed, matching the initial
  `guard.check()` rejection shape) and the pre_approve-through-
  submit_order section is wrapped in the same `kill_switch_lock()`.
- **Bonus fix found in the same block, unrelated to the race:**
  `trade_tool.py`'s successful-order response dict had a duplicate
  `"status"` key -- `"status": "submitted"` followed later by
  `"status": order.get("status", "")`, so the broker's raw order status
  (e.g. `"accepted"`/`"filled"`/`"pending_new"`) silently overwrote the
  tool's own `"submitted"` outcome. A caller checking `status ==
  "submitted"` to confirm a new order was created never actually saw
  that value once a real order came back. Renamed the broker's own field
  to `"broker_status"` -- both pieces of real information kept, no
  collision. Confirmed nothing depended on the old (buggy) behavior
  before changing it (grepped every real "submitted" reference across
  the codebase).

## Why this closes the gap completely, not just narrows it

Before: two independent operations (check, then act) with nothing
between them but proximity in the source file -- proximity doesn't
prevent another process from acting in between.

After: `halt_trading()` and every check-then-act critical section
compete for the same OS-level lock. If `halt_trading()` wins the race for
the lock, the critical section's fresh check sees the halt and takes the
safe branch. If the critical section wins, `halt_trading()` blocks until
it releases -- the halt still lands, just a few milliseconds later, after
the in-flight decision (which was already correctly gated by whatever
the kill switch's state was at the moment the lock was acquired)
finishes. Genuinely mutually exclusive, not probabilistically unlikely.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-agent/vinu_agent/broker/kill_switch.py` | modified | `kill_switch_lock()` (new), `halt_trading()`/`resume_trading()` now acquire it |
| `vinu-components/vinu-agent/vinu_agent/agent/capital_allocator_hook.py` | modified | check-through-transition wrapped in `kill_switch_lock()` |
| `vinu-components/vinu-agent/vinu_agent/tools/trade_tool.py` | modified | `pre_approve()`'s result now checked; pre_approve-through-submit_order wrapped in `kill_switch_lock()`; duplicate `"status"` key fixed (`"broker_status"`) |
| `vinu-components/vinu-agent/tests/test_kill_switch.py` | new | 5 tests: halt/resume round-trip still works (global + scoped), global-precedence-over-scoped unchanged, and two real threading tests proving mutual exclusion (a second lock acquirer blocks until the first releases; `halt_trading()` blocks while a critical section holds the lock) |
| `vinu-components/vinu-agent/tests/test_trade_tool.py` | new | 4 tests: successful submission, rejection at the initial check, rejection at `pre_approve` even though the initial check passed (the real bug, proven directly), and lock-ordering (`lock_acquired -> pre_approve -> submit_order -> lock_released`) |

## Test results

```
vinu-agent: 650 -> 659 passed (full suite; 9 new tests)
```

No regressions. `test_capital_allocator_hook.py` and `test_order_guard.py`
(both touch code this change modified) confirmed passing before the
full-suite run.

## Known follow-ups (not blocking, not silently dropped)

- **The lock's wait is unbounded in theory** -- every real critical
  section it guards today is local disk/in-memory work (no network I/O),
  so the practical wait is short, but nothing currently times out an
  acquisition. Worth adding a timeout if a future critical section ever
  does real I/O while holding this lock -- none does today.
- **Only two call sites were wrapped** (`capital_allocator_hook.py`,
  `trade_tool.py`) -- these are the two real check-then-act sequences
  found by reading the broker-adjacent code directly. If a future
  caller adds a third kill-switch-gated action, it needs to acquire
  `kill_switch_lock()` too, same pattern -- not automatic, has to be
  applied deliberately at each new site.
- **`OrderGuard.check()`'s other gates** (mandate limits, market hours,
  active-artifact check, portfolio concentration) were not evaluated for
  their own check-then-act windows this pass -- scope was specifically
  the kill switch, the one gate explicitly flagged as safety-critical
  (02-guard-rail.md) and named in the question that prompted this fix.
