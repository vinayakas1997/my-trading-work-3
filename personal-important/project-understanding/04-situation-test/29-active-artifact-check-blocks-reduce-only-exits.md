# Situation 29: can a position survive its own strategy being retired?

## Question

A third instance of the pattern situations 15 and 22 already found twice:
`require_active_artifact` blocks orders for a symbol with no ACTIVE
research-promoted strategy artifact. Does it exempt `reduce_only`, or does
it -- like the short-selling check and the ticker allowlist before their
fixes -- block exits too?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`if mandate.require_active_artifact:` block.

## How tested

Real `OrderGuard.check()`, a real `SqliteStrategyStore` (temp file, no
artifacts registered at all -- simulating a strategy that was archived
after opening a position). Ran a `reduce_only` sell and a normal buy.

## Observed (before the fix)

```
No active artifact, REDUCE-ONLY sell (closing a position from a now-retired strategy):
    allowed=False | "AAPL has no ACTIVE strategy artifact..."
```

## Verdict: real bug, fixed (third occurrence of the same pattern)

Same reasoning as situation 22's `allowed_tickers` fix:
`require_active_artifact` governs whether a symbol may be *opened* under a
research-promoted strategy, not whether an already-open position is
untouchable. A strategy can fail its ongoing monitoring, get archived, or
simply retire (its artifact leaving `ACTIVE`) while a position it opened
earlier is still held -- exiting that position must not depend on the
strategy still being active today.

**Fixed**: `if mandate.require_active_artifact and not reduce_only:` (was
missing the `reduce_only` exemption). Verified: a `reduce_only` sell with
no active artifact now clears; a normal buy with no active artifact is
still correctly blocked. Two tests added to
`tests/test_order_guard.py::TestRequireActiveArtifact` (now 7 tests, up
from 5, all passing) alongside the pre-existing coverage for the ACTIVE/
BENCHING/disabled/fail-open cases, which are all unaffected by this
change.

Three real, independent instances of the exact same missing-exemption
pattern (situations 15, 22, 29) found across this one file in one audit
session is itself worth noting: it suggests the "reduce_only is always
exempt" rule was applied deliberately and explicitly to some checks (kill
switch, consent expiry, portfolio-wide daily cap, risk-budget halt -- all
of which have their own comment saying so) but never systematically swept
across every check in the method when it was established as a house rule.
