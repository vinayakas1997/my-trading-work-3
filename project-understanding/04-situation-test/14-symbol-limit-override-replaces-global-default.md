# Situation 14: does a per-symbol limit override really replace the global mandate default?

## Question

`OrderGuard._effective_limit()` (C7) is supposed to let an operator set a
tighter `max_order_value` for one symbol (e.g. thin liquidity) without
touching the mandate's global default for every other symbol. Does the
override actually take effect at `check()` time, for that symbol only,
while every other symbol keeps using the mandate's global number?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard._effective_limit()`
+ its call site for `max_order_value` inside `check()`.

## How tested

Real `SymbolLimitStore` (temp SQLite file), a mandate with a generous
global `max_order_value=$100,000`, and a per-symbol override on AAPL only
(`max_order_value=$500`, via the store's real `.set()`). Ran the same $600
order for both AAPL (should be rejected by the tighter override) and MSFT
(no override -- should pass under the generous global default).

## Observed

```
AAPL (per-symbol override max_order_value=$500), order value $600:
    allowed=False, reason='Order value 600.00 exceeds max_order_value 500.00'
MSFT (no override, global max_order_value=$100000), same $600 order:
    allowed=True
```

## Verdict: matches the documented design

The override is symbol-scoped exactly as intended -- the identical $600
order clears for MSFT and fails for AAPL on the same `OrderGuard` instance,
confirming `_effective_limit()` reads the per-symbol store first and only
falls back to the mandate default when there's no override for that
specific symbol, not as a global replacement.
