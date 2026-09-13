# Situation 30: after finding the pattern three times, does it hold everywhere it should?

## Question

Situations 15, 22, and 29 each found the exact same missing-exemption
pattern in a different check (short-selling, ticker allowlist,
active-artifact) -- all three governing whether a symbol is sanctioned to
be *opened*, and all three wrongly extending that restriction to
`reduce_only` exits too. Before assuming every check in `OrderGuard`
should exempt `reduce_only`, it's worth checking one that shouldn't:
`require_market_open`. Unlike the other three, "the market is closed" is
not a policy restriction on what may be opened -- it's a hard fact about
whether *any* order can execute right now, in either direction. Does the
real code correctly NOT exempt `reduce_only` here, and is that the right
call?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`if mandate.require_market_open:` block / `_check_market_open()`.

## How tested

Real `OrderGuard.check()`, a mocked broker clock reporting the market
closed. Ran both a `reduce_only` sell and a normal buy.

## Observed

```
market closed, REDUCE-ONLY sell: allowed=False | "Market is closed..."
market closed, NEW buy: allowed=False | "Market is closed..."
```

Both blocked identically -- no `reduce_only` exemption, and none was
added.

## Verdict: matches the design, and it's the right design -- this completes the sweep

This is the fourth check examined for this exact question in this audit,
and the first of the four that's correct as-is without any exemption.
The distinction that separates it from situations 15/22/29: `allow_short`,
`allowed_tickers`, and `require_active_artifact` are all *policy*
decisions about which new exposure an operator has sanctioned -- an
exit was never actually constrained by any of them in principle, only by
an incomplete implementation. `require_market_open` is different in kind:
it reflects whether the broker can execute an order *at all* right now,
a fact that applies equally to both directions (the check's own message,
"Set require_market_open: false... to allow orders that queue for open",
confirms the intended alternative is queuing the order for the next
session, not bypassing the constraint for exits specifically -- there is
no broker-side "let me out even though the market's shut" mechanism this
check could defer to). Confirms the reduce_only-exemption pattern found
three times in this audit was correctly scoped to policy-type checks all
along, not something that should be applied blindly to every check in
this method -- exactly the same judgment call situation 11 made for
`blocked_tickers`/`IGNORED` earlier in this audit.
