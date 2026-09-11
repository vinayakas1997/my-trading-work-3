# Scenario 06 — Broker-side stop already closed the position overnight

## Plan

Written before anything is fixed (the bug this section documents was found
while designing this scenario, verified by reading the real code, not
assumed — the fix below is written up in Reasoning/Action Taken after
building and running the proving test).

This is the flagged gap from scenario 01: does `_reconcile_book_with_broker`
correctly recover when the broker-side resting stop (the "protected even if
this process is down" catastrophic backstop) has *already* closed a
position before the next cycle even runs — the realistic overnight case?

Re-verified against the real code before writing this: `_fetch_broker_positions()`
returns `{}` (empty dict) in **two structurally different situations** that
the rest of the code cannot currently tell apart:
1. The HTTP call to `/agent/broker/positions` **succeeds** (200) and the
   broker genuinely reports zero open positions — a *confirmed* flat
   account. This is exactly what a resting stop firing overnight on your
   only open position produces.
2. The HTTP call **fails** (exception, non-200, or a malformed body) — an
   *unknown* state, not a confirmed one.

Both currently collapse to the same `{}` sentinel, and both call sites that
consume it treat `{}` as falsy:
- `_reconcile_book_with_broker`: `if RECONCILE_AUTOCORRECT and actual:` —
  skips auto-correction on `{}`, logging "can't tell a real flat account
  from a failed fetch." **This means a single-position account whose only
  holding was closed by the overnight stop is treated identically to a
  broker outage — the stale book position is never auto-closed, forever,
  by this mechanism.**
- `_broker_close_plan`: `if not broker: return ..., "no_broker_view"` — a
  later invalidation-exit attempt on that same stale position falls back to
  sending a REAL `reduce_only` sell order for the book's believed qty,
  against an account that (per this specific symbol) is empty. This is
  **exactly the failure mode `_broker_close_plan`'s own docstring says it
  was built to prevent** ("observed live: a reduce_only SELL for the book
  qty on an already-flat account opened a short") — but that protection
  only engages when the broker snapshot is non-empty *for other symbols*
  (so `broker.get(symbol, 0.0)` can resolve to a real, distinguishable
  `0.0`). When the account is fully flat (this was the only position), the
  snapshot is `{}` overall, and the exact bug the function exists to
  prevent becomes reachable again through the ambiguity above.

Both call sites are correct in the genuine-failure case (fail open, don't
assume), and this is a real, previously-known, deliberate tradeoff (the
code's own comment says so) — but the two situations it lumps together are
NOT actually indistinguishable at the source: `_fetch_broker_positions()`
itself discards the distinction. A 200 response with an empty JSON list
**is** a confirmed, trustworthy signal (the broker successfully told us
"nothing here"); only a non-200 / exception is genuinely unknown. That
distinction is recoverable with no new endpoint and no new HTTP call —
`_fetch_broker_positions()` just needs to stop conflating the two.

**The fix** (built before writing Execution Result, same scope-discipline
as the audit's other in-place fixes): `_fetch_broker_positions()` now
returns `dict[str, float] | None` — `None` only for a genuine failure
(exception, non-200, or unexpected body shape), and a dict (possibly `{}`)
for any confirmed 200 response. `_reconcile_book_with_broker` now gates
auto-correction on `actual is not None` instead of truthiness, so a
confirmed-flat account correctly auto-closes a stale position.
`_broker_close_plan` now gates its `no_broker_view` fallback on
`broker is None` instead of `not broker`, so a confirmed-flat account
correctly falls through to the `broker_flat` branch (no order sent, book
closed) rather than the `no_broker_view` branch (a real sell order sent
against nothing to sell). One other call site (`pre_signed` in
`_maybe_enter`) was calling `.get()` directly on the return value and
would have crashed on the new `None` return — guarded with `or {}`
(fail-open, matches its existing conservative default).

## Expected Result

Two sub-scenarios, both driven through the real methods (not reimplemented):

1. **Confirmed flat, single open position (the realistic overnight-stop
   case)**: an open AAPL long position, `/agent/broker/positions` returns
   a real 200 response with an empty list (confirmed flat, not a fetch
   failure). `_reconcile_book_with_broker` must now auto-close the stale
   AAPL book position (`closed_to_match_broker`), not skip it. Separately,
   if an invalidation were to fire on this same position before
   reconciliation runs, `_broker_close_plan` must resolve to
   `broker_flat` (book-only close, no order sent) rather than
   `no_broker_view` (a real sell order sent against a flat account).
2. **Genuine fetch failure (the pre-existing, still-correct case)**: the
   HTTP call to `/agent/broker/positions` raises or returns non-200.
   `_reconcile_book_with_broker` must still skip auto-correction (fail
   open, unknown state), and `_broker_close_plan` must still fall back to
   `no_broker_view`. This sub-scenario exists specifically so the fix
   doesn't accidentally erase the genuine-failure protection while fixing
   the confirmed-flat case.

## Execution Result

Fix built in `vinu_live/trade_plan/orchestrator.py` (`_fetch_broker_positions`,
`_broker_close_plan`, `_reconcile_book_with_broker`, plus a guard on the
`pre_signed` call site that would otherwise have crashed on the new `None`
return). Proven two ways:

**New dedicated scenario test**, `test_pre_live_scenarios.py::TestScenarioBrokerStopClosedOvernight`, 3 tests:
```
test_reconciliation_auto_closes_the_stale_position_when_broker_confirms_flat PASSED
test_invalidation_exit_on_the_same_stale_position_never_sends_a_phantom_order PASSED
test_genuine_broker_failure_still_falls_back_to_no_broker_view PASSED
```

**Existing unit-level coverage**, split to cover both branches distinctly
(`test_trade_plan_orchestrator.py`): `test_reconcile_auto_corrects_on_a_confirmed_flat_broker_snapshot`,
`test_reconcile_skips_on_a_genuine_broker_fetch_failure`,
`test_broker_close_plan_no_view_falls_back_to_book` (now genuinely unknown,
not `{}`), `test_broker_close_plan_confirmed_flat_account_is_broker_flat`
(new) — all passing.

The fix had a wide blast radius: 19 pre-existing tests across both test
files used a `/broker/positions` 200-with-`[]` mock as a generic "don't
care about broker positions" convenience default -- which, once the fix
made that response mean something real (confirmed-flat), needed updating
to reflect what each test actually intended: most got a broker mock that
actually matches the book (their real point was untouched -- e.g. "does
the spread gate block an exit," not broker-flat recovery); two tests that
were genuinely testing the old no_broker_view fallback (scenario 01's own
`TestScenarioGapDownCrash`) were switched to a genuine transport-error mock
so they keep testing exactly what they always intended, undiminished.

Full `vinu-live` suite: 317 passed (2 pre-existing, unrelated `test_auth.py`
failures — same baseline throughout this audit; 8 net new tests added by
this fix's own coverage).

## Reasoning

This scenario found a real, previously-live bug, not just an untested
path: `_fetch_broker_positions()` collapsed two structurally different
situations ("the broker successfully confirmed zero positions" vs "we
could not reach the broker") into the same `{}` sentinel, and both
consumers of it treated that sentinel as "unknown, don't touch." For a
single-position account -- the realistic case for anyone actually running
this with real money at modest scale, not a large multi-symbol book --
this meant the specific case this scenario exists to test (the resting
stop firing overnight, the account going genuinely flat) was **silently
indistinguishable from a broker outage, forever**, by the one mechanism
that exists to catch it. Worse, if an invalidation later fired on that
same stale position, `_broker_close_plan` would take the `no_broker_view`
fallback and send a real `reduce_only` sell order against an account with
nothing to reduce for that symbol -- reopening the exact "opened a short
on an already-flat account" failure mode that function's own docstring
says it was built to prevent, through the one gap that ambiguity left.

The fix required no new endpoint, no new data -- the broker already tells
the difference (a 200 vs a transport error/non-200) at the one place that
was throwing it away. This is the same shape as this whole audit's other
fixes: not inventing new protection, but making an already-intended
distinction actually reach the code that needed it.

Also worth recording honestly: this fix changed the observable outcome of
`TestScenarioGapDownCrash` (scenario 01) and `TestScenarioKillSwitchMidCycle`
(scenario 02) if their broker mocks had been left unchanged -- both used
the same `[]` convenience default, which would have started resolving to
`broker_flat` (no order, book-only close) instead of the `no_broker_view`
fallback (a real order) those scenarios were built to prove. Both were
updated to keep testing exactly what they always said they were testing
(scenario 01's stated intent was explicitly the `no_broker_view` fallback,
so its mock now uses a genuine transport error instead of `[]`; scenario
02's intent was the halt not blocking a real exit, so its mock now shows
a broker that actually holds the position). Neither scenario's documented
conclusion changes -- both still hold -- but this is noted here for the
record since a future reader diffing the orchestrator against those
scenario docs should know why those particular mocks look different now.

## Action Taken

**Fixed** -- `vinu_live/trade_plan/orchestrator.py`: `_fetch_broker_positions`
now returns `dict[str, float] | None` (`None` only for a genuinely unknown
state), `_broker_close_plan` and `_reconcile_book_with_broker` now branch
on that distinction instead of truthiness. 8 new tests added across
`test_pre_live_scenarios.py` and `test_trade_plan_orchestrator.py`; 19
pre-existing tests updated to reflect what they actually intended to test
now that the ambiguity they were incidentally relying on is gone.

No new gaps flagged from this one -- the genuine-failure fallback
(`no_broker_view`) is unchanged and still correctly conservative.
