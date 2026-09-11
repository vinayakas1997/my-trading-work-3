# Scenario 01 — Gap-down crash

## Plan

Written before anything is run.

An open long AAPL position, entered at $100, with:
- A plan `invalidation_conditions` threshold of `unrealized_pnl_pct <= -0.08` (same shape already proven in `test_pre_live_scenarios.py`'s invalidation scenario, but that one only tested a modest -10% move).
- One single bar where price gaps straight down to $75 — a **-25% crash in one print**, not a gradual multi-bar slide. This is the realistic shape of an actual gap-down (an overnight move, a halt-and-reopen, a flash crash), not a steady decline the system has all day to react to.
- `/broker/positions` returns `[]` (broker view unavailable/ambiguous — same convention the existing invalidation test uses), so `_broker_close_plan` takes its documented `no_broker_view` fallback: close the full book qty.
- No prior realized losses this session (`daily_realized_pnl = 0`), so the breaker's daily-loss check has nothing to trip on from *this* unrealized move alone.

Drives the real `_evaluate_open_position` directly (same convention every scenario in this suite uses) — not a reimplementation.

## Expected Result

1. `_evaluate_open_position` must detect the invalidation on the **very first cycle** that sees the $75 print — no assumption anywhere in the code that a crash arrives gradually over several bars.
2. The breaker must **not** block the exit — `daily_realized_pnl` is still 0 at this point (the loss is unrealized until the exit fills), so `check_limits`'s daily-loss check has nothing to trip on, and the exit proceeds normally (not even needing the `reduce_only` HALT exemption, since there's no HALT to exempt from in this scenario).
3. A real `reduce_only` sell order is submitted for the full 10-share position.
4. The book position is closed (`list_open_positions` returns empty for AAPL afterward).
5. The returned action is `invalidation_exit`, not `exit_not_filled` or `exit_blocked_by_breaker`.

## Execution Result

Built as `vinu-live/tests/test_pre_live_scenarios.py::TestScenarioGapDownCrash`, 2 tests, run against the real `_evaluate_open_position`:

```
tests/test_pre_live_scenarios.py::TestScenarioGapDownCrash::test_single_bar_25pct_crash_exits_on_the_very_first_cycle_that_sees_it PASSED
tests/test_pre_live_scenarios.py::TestScenarioGapDownCrash::test_no_realized_daily_loss_means_the_breaker_does_not_block_the_exit PASSED
```

Full `vinu-live` suite after: 307 passed (2 pre-existing, unrelated `test_auth.py` failures — same baseline confirmed throughout this whole audit).

Both assertions from Expected Result held exactly, first try — no fix was needed:
- The -25% single-bar crash triggered `invalidation_exit` on the very first cycle, no multi-bar assumption anywhere in `_evaluate_open_position`'s invalidation check.
- The exit sold the full 10-share position, `reduce_only=True`, correctly reconciled through `_broker_close_plan`'s `no_broker_view` fallback (matches the existing, milder invalidation test's already-proven path — a crash of this size doesn't take a different code path than a modest move, it's the same check with a bigger number).
- The breaker did not block it — `daily_realized_pnl(self._book)` is 0 before the exit fills, so `_check_daily_loss` (which only looks at *realized* P&L, not unrealized) had nothing to trip on. Confirmed by reading `breaker/engine.py`'s `_check_daily_loss` directly before writing the Expected Result, not assumed.

## Reasoning

This scenario didn't find a bug — it confirmed a real, valuable fact: the invalidation-exit mechanism has no implicit size or gradualness assumption baked in. A -10% slide and a -25% single-bar crash go through the exact same code path (`unrealized_pnl_pct <= threshold`, computed fresh from whatever the latest price is), so there was never a hidden "only reacts to gradual moves" gap to find. That's a genuinely reassuring result, not a non-result — it's exactly the kind of thing a pre-live check exists to confirm *before* trusting it, rather than finding out during an actual crash.

Worth being honest about the boundary of what this scenario tested: it proves the **orchestrator's own cycle-based invalidation check** reacts correctly to any size of adverse move. It does **not** test the broker-side resting stop order itself (the "protects you even if this process is down" backstop from the entry scenario) — that order lives entirely at the broker and executes independent of any Python code here; there is no way to observe whether it actually would have fired first in a real crash from inside this mocked harness. That's a separate, real gap worth its own scenario later (see Action Taken).

## Action Taken

**No fix needed** — the real behavior matched the known-correct answer on the first run.

**Flagged for later, not this scenario's scope**: whether `_reconcile_book_with_broker()` correctly recovers when the broker-side resting stop has *already* closed a position before the next cycle even runs (the realistic "protected even if this process is down" case). Found while designing this scenario: `_fetch_broker_positions()` returns `{}` both when the broker is genuinely flat AND when the fetch fails — the code already documents this as a deliberate tradeoff ("can't tell a real flat account from a failed fetch," `orchestrator.py`'s own comment on `_reconcile_book_with_broker`), not a bug, but it's a real, non-obvious behavior worth its own dedicated scenario rather than folding into this one. Candidate for scenario 06.

**2026-09-11 addendum, from scenario 06**: that "deliberate tradeoff" turned out to be a real, fixable ambiguity, not an inherent limitation — see `06-broker-stop-closed-overnight/scenario.md`. `_fetch_broker_positions()` now distinguishes a confirmed-flat account from a genuine fetch failure. This scenario's own test (`TestScenarioGapDownCrash`) was exercising exactly the `no_broker_view` fallback described above, so its mock was updated (a genuine transport error instead of a 200-with-`[]`) to keep testing precisely that, undiminished — this scenario's documented conclusion is unchanged and still holds. Noted here so a future reader isn't surprised the test's mock looks different from what's described above.
