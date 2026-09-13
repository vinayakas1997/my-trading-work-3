# Situation 27: does the drawdown breaker actually avoid the same re-notify-every-cycle trap?

## Question

After finding situation 24's real gap (a persisting reconciliation drift
re-notified every cycle because nothing dedup'd it), a natural question
about a sibling mechanism in the same file: `_check_breaker()`'s real
kill-switch engagement (`_engage_real_halt()`) only fires `if verdict ==
BreakerVerdict.HALT and not was_halted:` -- edge-triggered, by
inspection. Does that actually hold under real repeated calls while
still halted, and does a failure to reach the kill-switch endpoint still
correctly halt the LOCAL breaker state (fail toward safety) even though
the cross-process kill switch didn't get engaged?

## Where

`vinu-live/vinu_live/trade_plan/orchestrator.py::_check_breaker()` /
`_engage_real_halt()`.

## How tested

This one already had dedicated, real tests from earlier work in this
session (`tests/test_trade_plan_orchestrator.py::TestBreakerEngagesRealHalt`)
-- rather than re-deriving them, ran them directly to confirm they still
pass after this session's other changes to the same file (situation 24
touched `_reconcile_book_with_broker` in the same class): a fresh breach
engages the real halt exactly once; an already-halted state makes zero
further HTTP calls on a repeat check; a failed halt-engage call (404) still
leaves the local breaker state halted; an `ALLOW` verdict never calls halt
at all.

## Observed

```
tests/test_trade_plan_orchestrator.py::TestBreakerEngagesRealHalt::test_new_breach_engages_the_real_kill_switch PASSED
tests/test_trade_plan_orchestrator.py::TestBreakerEngagesRealHalt::test_already_halted_does_not_re_engage_every_cycle PASSED
tests/test_trade_plan_orchestrator.py::TestBreakerEngagesRealHalt::test_halt_engage_failure_does_not_raise PASSED
tests/test_trade_plan_orchestrator.py::TestBreakerEngagesRealHalt::test_allow_verdict_never_calls_halt PASSED
```

## Verdict: matches the documented design, confirmed still holding

Unlike situation 24's reconciliation-drift notification (which claimed
this same "doesn't repeat every cycle" property in a comment but didn't
actually have it), the breaker's halt engagement genuinely does -- the
`was_halted` check is real, tested, and still passes after this session's
edits elsewhere in the same file. Also confirms `_engage_real_halt()`
fails toward safety on its own network problem: the *local* `BreakerState`
is set by `check_limits()` before `_engage_real_halt()` is even attempted,
so a failed cross-process kill-switch call (logged at `ERROR`, explicitly
calling out that "OrderGuard and other order paths are NOT halted") still
leaves this orchestrator's own new-entry path blocked -- a partial failure
degrades to "only one of two enforcement points is active," never to "no
enforcement at all."
