# Situation 5: is the risk-budget HTTP call really fetched only once per order?

## Question

`OrderGuard._fetch_risk_budget()`'s docstring claims `_risk_budget_multiplier`
(called from `position_size_multiplier()`, when soft-limits are on) and
`_check_risk_budget` (called from `check()`) "both run against the same
OrderGuard instance for the one symbol a single `trade_tool.py` execute()
call is ever about, so a per-instance memo here is exactly enough to turn
two network round-trips per order into one." Does the real memo actually
dedupe the call, or does the second one still hit the network?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard._fetch_risk_budget()`,
`_risk_budget_multiplier()`, `_check_risk_budget()`.

## How tested

Real `OrderGuard` instance; `requests.get` patched with a call-counting
stub (the only network boundary) so every real call, cached or not, is
visible. Called `position_size_multiplier()` then `check()` for the same
symbol on the same instance -- the exact two-call sequence the docstring
describes.

```python
guard = OrderGuard(...)
guard.position_size_multiplier("AAPL", "buy", qty=10, price=100.0)
guard.check("AAPL", "buy", qty=1, price=100.0)
```

## Observed

```
position_size_multiplier -> multiplier=0.5, binding=risk_budget
check() -> allowed=True
total /portfolio/risk/status calls across BOTH methods on one instance: 1
```

## Verdict: matches the documented design

The memo works as claimed -- one real network round trip serves both
callers on the same `OrderGuard` instance. Confirms the memoization comment
in the source isn't just aspirational.
