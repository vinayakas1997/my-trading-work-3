# Situation 9: does the "equity unreadable" risk-budget branch really fail closed?

## Question

Almost every broker/service-dependent check in `OrderGuard` fails *open*
(allows the order, logs a warning) if the dependency is unreachable --
that's the stated posture throughout the file. `_check_risk_budget()` has
one deliberate exception: if vinu-portfolio responds with HTTP 200 but
`aggregate.status == "no_equity"` (broker equity itself couldn't be read),
the comment says this fails *closed* instead, because an existing
TIER_HALT can't be ruled out. Does the real code actually take the opposite
branch here, or does the "budget is None" fail-open path silently swallow
this case too (since a 200 response means `budget is not None`)?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard._check_risk_budget()`,
the `if budget.get("aggregate", {}).get("status") == "no_equity":` branch.

## How tested

Real `OrderGuard.check()`, `requests.get` patched to return a real 200
response (not an exception -- the critical distinction, since the
`_fetch_risk_budget` fail-open path only triggers on an actual exception)
with `{"symbols": [], "aggregate": {"status": "no_equity"}}`. Ran both a
normal buy and a `reduce_only` sell against it.

## Observed

```
NEW buy, equity unreadable: allowed=False, reason="Cannot verify
    risk-budget status for AAPL -- vinu-portfolio could not read current
    account equity, so an existing TIER_HALT can't be ruled out. Blocking
    new/increasing orders until equity is readable again; risk-reducing
    orders are still allowed."
REDUCE-ONLY sell, same state: allowed=True
```

## Verdict: matches the documented design

The fail-closed branch is real and correctly distinguished from the
general fail-open posture -- a subtle thing to get right (both paths
return from the same function, on data from the same HTTP call, and only
diverge on one string field), and it does. The `reduce_only` exemption
still applies on top of the fail-closed branch, consistent with every
other exit-path exemption in this class -- `_check_risk_budget` is never
even called for `reduce_only` orders (`check()`'s `if not reduce_only:`
guard around it), so the exemption is structural, not something this
specific branch had to re-implement.
