# Situation 10: is an unpriceable order really rejected outright, except for reduce_only?

## Question

`OrderGuard.check()`'s order-value determination has a deliberate fail-CLOSED
design: `value = max(estimated_value or 0.0, qty * (price or 0.0))`, and if
that comes back `<= 0.0` for a non-`reduce_only` order, it's rejected
outright ("Cannot determine order value") rather than silently treated as a
$0 order that would trivially clear every notional cap. Does a `reduce_only`
order with the same missing price/estimated_value actually get through, as
the `and not reduce_only` condition implies?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`if value <= 0.0 and not reduce_only:` block.

## How tested

Real `OrderGuard.check()` called with `price=None` and no `estimated_value`
for both a normal buy and a `reduce_only` sell, mandate configured so no
other check could produce a `False` first (percentage-based checks
disabled, since they'd also see `value == 0` and trivially pass anyway, but
isolating this specifically).

## Observed

```
NEW buy, unpriceable: allowed=False, reason='Cannot determine order value
    -- no usable price or estimated_value. Supply a limit price (or
    estimated_value) so the notional cap can be enforced.'
REDUCE-ONLY sell, unpriceable: allowed=True
```

## Verdict: matches the documented design

Confirms the `A36` fix's stated intent: an unpriceable normal order can't
silently bypass the notional cap by collapsing to `value=0`, but a
`reduce_only` order (which by definition isn't opening or growing
exposure) isn't held hostage by a missing price either. Both halves of the
`and not reduce_only` condition do real work, not just one of them.
