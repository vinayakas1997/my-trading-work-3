# Situation 24: did my own #8 fix's comment describe real behavior, or wishful thinking?

## Question

While investigating situation 23 (the shared notify front door is
permissive by default), a comment I wrote earlier this session, right next
to the code it describes, stood out for a second look:
`_notify_reconciliation_drift()`'s docstring claims delivery is "deduped
per (symbol, action) on that side, so a condition that persists across
cycles doesn't re-notify every cycle." Situation 23 just showed the shared
`_deliver_notification()` dedup window is 0/disabled by default. Did I
write a comment describing behavior that was never actually there?

## Where

`vinu-live/vinu_live/trade_plan/orchestrator.py::_reconcile_book_with_broker()`
/ `_notify_reconciliation_drift()`.

## How tested

Real `TradePlanOrchestrator._reconcile_book_with_broker()`, called 3 times
in a row against a *long-lived* orchestrator instance (matching production
-- `cli.py` constructs one `TradePlanOrchestrator` and calls `.cycle()` on
it in a loop, never a fresh instance per cycle) with the same persisting
phantom-position drift (`TSLA` held at the broker, no book position) each
time, counting real POST calls to `/notify/reconciliation-drift`.

## Observed (before this fix)

3 identical cycles produced 3 separate `POST /notify/reconciliation-drift`
calls -- the comment's claim was false. There was no per-(symbol, action)
dedup anywhere in this code path; it relied entirely on the shared notify
gate, which (situation 23) doesn't dedup unless an operator opts in.
Combined with the 300-second default cycle interval, this is the same
spam risk situation 23 quantified, but for a claim I had explicitly made
in writing about my own fix, not just an unstated default.

## Verdict: real bug in my own earlier work, found by testing my own comment, fixed

**Fixed**: added real, edge-triggered, per-instance dedup in the
orchestrator itself -- `self._recon_drift_notified: set[tuple[str, str]]`,
updated every cycle to the current set of alert-worthy `(symbol, action)`
pairs. A pair only triggers a notification on the cycle it *first*
appears; while it stays present, later cycles skip it; if it clears and
later recurs, it's treated as a new occurrence and notifies again. This
lives at the orchestrator level (not the shared gate) because the
orchestrator instance is already long-lived across cycles -- the exact
same pattern `self._recently_traded` (a few lines above, in the same
`__init__`) already uses for its own per-instance, cross-cycle state.
Corrected the docstring to describe where the dedup actually lives now,
instead of restating an untrue claim about the shared gate.

Added two tests to `tests/test_trade_plan_orchestrator.py`: a persisting
drift across 3 consecutive real cycles notifies exactly once; a drift that
clears and later recurs notifies again (confirming the suppression isn't
permanent). Full reconciliation test slice: 22 passed (up from 20). Full
`test_trade_plan_orchestrator.py` suite: 157 passed.

This is the fourth real bug found in this audit traceable to my own
earlier work this session (after situations 15, 17, and 22's underlying
cause) -- and the second one found specifically by re-examining a comment
I'd written, rather than the code's logic directly. Comments describing
"this is deduped" or "this fails open" are claims just like code is; this
session's whole methodology (test it, don't just read it) applies equally
to prose I wrote about my own fixes.
