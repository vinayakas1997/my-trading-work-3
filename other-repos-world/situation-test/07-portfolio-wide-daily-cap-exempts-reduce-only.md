# Situation 7: does the portfolio-wide daily order cap really exempt reduce_only?

## Question

`OrderGuard.check()`'s `max_daily_orders_portfolio` block has a comment
saying it's "Exempt reduce_only: a portfolio-wide overtrading cap must
never be the thing that stops you from de-risking on a bad day." Does a
reduce_only order really still clear this check once the portfolio-wide cap
is already exhausted, or does the exemption only cover the *reasoning*, not
the actual code path?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`if mandate.max_daily_orders_portfolio > 0 and not reduce_only:` block.

## How tested

Real `OrderGuard` + real `DailyLimitStore`, `max_daily_orders_portfolio=2`.
Drove the real portfolio-wide count up to the cap with two different
symbols via `pre_approve()` (which actually records the order, not just
checks it), then tried a third order for a brand-new symbol two ways: a
normal buy, and a reduce_only sell.

```python
mandate = TradingMandate(max_daily_orders_portfolio=2, max_daily_orders=100, ...)
guard.pre_approve("AAPL", "buy", qty=1, price=10.0)   # count -> 1
guard.pre_approve("MSFT", "buy", qty=1, price=10.0)   # count -> 2 (cap reached)
guard.check("NVDA", "buy", qty=1, price=10.0)                       # new buy
guard.check("NVDA", "sell", qty=1, price=10.0, reduce_only=True)    # reduce-only
```

## Observed

```
order 1 (AAPL buy): allowed=True
order 2 (MSFT buy): allowed=True
order 3, NEW buy (NVDA), cap already at 2/2: allowed=False,
    reason='Portfolio-wide daily order limit (2) reached across all symbols'
order 3, REDUCE-ONLY sell (NVDA), same cap state: allowed=True
```

## Verdict: matches the documented design

The exemption is real, not just a comment -- a reduce_only order for a
symbol that never even traded today still clears the check once the
portfolio-wide cap is blown, exactly as intended.
