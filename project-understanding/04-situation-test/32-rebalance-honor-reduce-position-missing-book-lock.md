# Situation 32: is every book mutation actually protected by the same lock?

## Question

`vinu-live/book/lock.py`'s own docstring recounts a real, previously
*observed live* incident: "a reconcile that `add_to_position` the same
delta twice, leaving the book at ~2x the broker before the next cycle
trimmed it back" -- exactly why `book_lock()` (a real cross-process
`fcntl.flock`/`msvcrt.locking`, same pattern as vinu-agent's
`kill_switch_lock()`) exists. `orchestrator.py` has 9 call sites that
mutate the book (`open_position`/`add_to_position`/`reduce_position`/
`close_position`); 8 of them wrap the call in `with
book_lock(self._book_lock_path):`. Does the 9th -- the rebalance-request-
honoring path, `_evaluate_rebalance_request`'s `reduce_position(...)`
call -- actually need it too, and is it missing?

## Where

`vinu-live/vinu_live/trade_plan/orchestrator.py::_evaluate_rebalance_request()`
(the `reduce_position(self._book, position.position_id, reduce_qty,
price)` call, originally with no `book_lock()` around it) +
`vinu-live/vinu_live/book/positions.py::reduce_position()` (a real
read-then-write: `get_position()` then compute new qty/realized_pnl then
`UPDATE`).

## How tested

First, isolated the underlying question from the orchestrator entirely:
real `BookBackend` against a temp SQLite file, a real position (qty=100),
two real threads each with their own `BookBackend` connection (mirroring
two different real callers/processes), both calling the real
`reduce_position(qty=30)` concurrently with **no** lock around either.

```python
def reducer(qty):
    own_book = BookBackend(book_path)
    barrier.wait()  # maximize the chance both reads land before either write
    reduce_position(own_book, pos.position_id, qty, price=155.0)
```

Then confirmed the fix by re-running the identical scenario with both
threads holding the real `book_lock()`.

## Observed

**Before the fix (no lock), 5/5 runs:**
```
per-thread results: [(30.0, 70.0), (30.0, 70.0)]
expected final qty after two -30 reduces from 100: 40.0
actual final qty in the book: 70.0
RACE CONFIRMED (lost update): True
```
Both threads read `qty=100` before either wrote, both independently
computed `100 - 30 = 70`, and the second `UPDATE` simply overwrote the
first with the same wrong value -- one of the two real reduces was
silently lost, while the `FILLS` table still recorded both fills
(a genuine book/fills-ledger inconsistency).

**With the lock held on both sides, 10/10 runs:** final qty correctly
`40.0` every time.

Confirmed the orchestrator's own production call site was the one
missing it by direct code inspection (8 of 9 mutation call sites already
wrapped; this one wasn't), then verified the fix end-to-end through the
real `_evaluate_rebalance_request()` path itself, not just the isolated
`reduce_position()` scenario.

## Verdict: real bug, fixed

The isolated concurrency test proves `reduce_position()` is exactly the
kind of read-then-write critical section `book_lock()`'s own docstring
says needs it -- this wasn't a theoretical concern, it's the *same* bug
shape `book_lock()` was built to close elsewhere, just not yet applied to
this one call site. **Fixed**: wrapped the `reduce_position(...)` call in
`with book_lock(self._book_lock_path):`, keeping the network I/O
(`await self._submit_order(...)`) outside the lock -- same convention
`_reconcile_book_with_broker()` already documents for its own broker
fetch. Added `tests/test_trade_plan_orchestrator.py::TestRebalanceRequestIntake::test_rebalance_honor_reduce_holds_book_lock`,
which spies on both `book_lock` and `reduce_position` to confirm the real
call order (`lock_acquired` -> `reduce_position` -> `lock_released`);
confirmed it actually fails against the pre-fix code (temporarily
reverted the fix, re-ran, watched it fail, restored it) before trusting
it as a real regression test. Full `test_trade_plan_orchestrator.py`
suite: 158 passed (up from 157).

This is the fifth real bug traced to the same general shape found across
this audit -- a specific call site skipping a protection every sibling
call site in the same file already applies (situations 15, 22, 29 for
`reduce_only` exemptions in `order_guard.py`; this one for `book_lock` in
`orchestrator.py`) -- reinforcing that "does every call site in this
family actually get the same treatment" is one of the highest-value
questions this kind of audit can keep asking.
