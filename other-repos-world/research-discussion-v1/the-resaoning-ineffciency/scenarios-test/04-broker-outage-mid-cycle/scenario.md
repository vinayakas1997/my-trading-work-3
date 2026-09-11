# Scenario 04 — Broker outage mid-cycle

## Plan

Written before anything is run. Re-verified against the real code first (not
assumed):

- `_check_broker_health()` probes `/agent/broker/account` once per `cycle()`,
  before the plan loop. A failing probe with `self._broker_ok_at == 0.0`
  ("never confirmed since start") sets `self._broker_degraded = True`
  immediately — no grace-window ambiguity to design around.
- `self._broker_degraded` is read in exactly one place:
  `_maybe_enter()` — it blocks new entries with
  `entry_blocked_by_broker_outage`. It has **zero** effect on
  `_evaluate_open_position()` / `_apply_invalidation()` — confirmed by grep,
  same pattern as scenario 02's `_trading_halted`. An existing test
  (`test_exit_never_gated_while_broker_degraded`) already proves this
  structurally, but with the order-submission POST mocked to always succeed
  regardless of the outage — i.e. it proves the *flag* doesn't gate the exit,
  not what happens when the outage is real enough to also break the exit's
  own order call.

That's the actual gap worth testing here, and it's a materially different
question from scenario 02 (kill switch): a kill switch is a *logical* halt —
the broker itself is reachable, `/agent/broker/order` still answers, and
`reduce_only` is exempted downstream. A **real broker outage** means
`/agent/broker/order` (the exit's own order call) is likely unreachable too —
it is the same broker connectivity, not a separate one. So unlike scenario
02, there is no reason to expect the exit to actually complete during a true
outage — the honest question is whether the code (a) still *attempts* the
exit rather than silently skipping it, (b) reports the failure truthfully
(`exit_not_filled`, not a false `invalidation_exit`), (c) leaves the book
position open rather than closing it on an unconfirmed fill, and (d) retries
correctly once the broker actually recovers.

Setup, one real `cycle()` call combining two symbols (same convention as
scenario 02):
- **MSFT**: no open position, an eligible entry signal. `/agent/broker/account`
  mocked to raise a transport error. `_broker_ok_at` left at its default
  `0.0` (never confirmed) so degraded triggers on this very first probe.
- **AAPL**: an open long position whose price breaches the plan's
  invalidation threshold (`unrealized_pnl_pct <= -0.08`, same shape as
  scenarios 01/02). `/broker/positions` also mocked to raise (consistent
  outage — `_broker_close_plan` falls back to `no_broker_view`, already
  proven safe in scenario 01). `/agent/broker/order` (the exit's own submit
  call) mocked to raise a transport error too, for this first pass — the
  same real connectivity that is down for the account probe.
- A second pass on the same AAPL position, same invalidation trigger, with
  `/agent/broker/order` now mocked to succeed — simulating the broker
  recovering before the next cycle — to confirm the exit isn't stuck or
  silently dropped once connectivity returns.

## Expected Result

1. `result["broker_health"]["degraded"]` is `True`.
2. MSFT's action is `entry_blocked_by_broker_outage`; no order is ever
   attempted for MSFT (`_submit_order` never reached for it).
3. AAPL: the exit is still *attempted* (not skipped because of
   `_broker_degraded` — that flag only gates `_maybe_enter`), but because the
   order POST itself transport-fails, the returned action is
   `exit_not_filled`, not `invalidation_exit`. The AAPL book position
   remains open afterward (`list_open_positions` still returns it) — no
   false claim of a completed exit.
4. No unhandled exception anywhere in the cycle — `result["status"]` stays
   `"ok"`, not `"failed"`.
5. On the second pass (broker recovered, order POST now succeeds), the same
   still-open AAPL position, still breaching the same threshold, now
   produces a real `invalidation_exit` and the book position closes — proving
   the earlier failed attempt didn't corrupt state or permanently drop the
   exit; it just correctly waits for the broker to actually be reachable.

## Execution Result

Built as `vinu-live/tests/test_pre_live_scenarios.py::TestScenarioBrokerOutageMidCycle::test_entry_paused_and_exit_fails_truthfully_then_recovers`:

```
tests/test_pre_live_scenarios.py::TestScenarioBrokerOutageMidCycle::test_entry_paused_and_exit_fails_truthfully_then_recovers PASSED
```

Full `vinu-live` suite after: 310 passed (2 pre-existing, unrelated `test_auth.py` failures — same baseline throughout this audit).

All five points from Expected Result held exactly, first try:
- `result["broker_health"]["degraded"]` was `True`, `orch._broker_degraded` was `True`.
- `result["status"]` stayed `"ok"` — the transport errors on `/broker/account`, `/broker/positions`, and `/broker/order` were all caught where the code already expects them, nothing propagated up to `cycle()`'s outer `except Exception`.
- MSFT: `entry_blocked_by_broker_outage`, no order attempted.
- AAPL: the exit was still attempted — `_submit_order`'s POST call was reached (confirmed via `post_mock.await_args_list`) — but came back `exit_not_filled` because the transport error raised inside `_submit_order`'s own `try/except` and was turned into `{"status": "error", ...}`, not a crash and not a false success. The book position stayed open.
- Second pass, broker reachable again: the same still-open AAPL position, same breached threshold, produced a real `invalidation_exit` and the book position closed.

## Reasoning

Same shape of result as scenarios 01-03: nothing was broken, and the value is in having actually forced the real failure mode rather than assuming the code handles it. The interesting design fact this confirmed, not just re-confirmed: `_broker_degraded` and "can the exit's own order call actually succeed" are two genuinely separate questions, and the code was never relying on the flag to protect the exit path — it was relying on `_submit_order`'s own `try/except` (which turns any transport failure into `{"status": "error", ...}` -> `exit_not_filled`) plus `_apply_invalidation` only closing the book position on `order_result.get("status") == "submitted"`. That combination is what actually keeps the book honest during a real outage, not the `_broker_degraded` flag itself — the flag only ever gated new entries.

This also clarifies something worth saying plainly for the trust question this whole audit is about: during a genuine, sustained broker outage, an already-breached invalidation **will not close the position** until the broker is reachable again — there is no way around that, no code fix changes it (you cannot fill an order the broker cannot receive). What this scenario proves is that the system fails *safely* in that window: it doesn't lie about having exited, it doesn't corrupt the book, and it keeps retrying every cycle rather than giving up after one failed attempt. The real backstop for that window is the static resting stop placed at entry (Scenario "Entry places the real catastrophic backstop") — which lives at the broker, not this process, and is exactly why that backstop exists as a separate, independent layer rather than relying on this cycle-based logic alone.

## Action Taken

**No fix needed** — the real behavior matched the known-correct answer on the first run.

No new gaps flagged from this one specifically, but it sharpens the stakes of the gap already flagged as scenario 06 (broker-side resting stop recovery): scenario 04 shows the cycle-based exit can stall during an outage; scenario 06 is what determines whether the broker-side resting stop actually protected the position during that same window. The two are complementary halves of the same real risk.
