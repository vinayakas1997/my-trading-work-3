# Situation 8: does a reduce_only order really survive a real kill-switch halt?

## Question

`OrderGuard.check()`'s kill-switch block has an explicit `reduce_only`
exemption for the default `VINU_LIVE_HALT_POLICY=entries_only` policy, with
a comment explaining why: exits must still work during a halt, or a
position could get trapped mid-crash by the same drawdown breaker that was
supposed to be protecting it. Does this actually hold up against the real,
filesystem-based kill switch (not a mocked `is_trading_halted`), end to
end?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`'s kill
switch block + `vinu-agent/vinu_agent/broker/kill_switch.py`'s real
`halt_trading()` / `is_trading_halted()` / `resume_trading()`.

## How tested

Real kill switch: called the actual `halt_trading(scope="AAPL")`, which
writes a real halt marker file, then ran real `OrderGuard.check()` calls
against it (no `is_trading_halted` mock anywhere in this one), for both a
normal buy and a `reduce_only` sell, then called the real
`resume_trading(scope="AAPL")` and re-checked.

## Observed

```
is_trading_halted('AAPL') via real kill_switch.py: True
NEW buy while halted: allowed=False, reason='Trading is halted by kill switch'
REDUCE-ONLY sell while halted: allowed=True
after resume_trading: is_trading_halted('AAPL') = False
```

## Verdict: matches the documented design, confirmed end-to-end

Not just "the code reads like it should do this" -- the real on-disk halt
marker, the real halt-check function, and the real guard all agree: a
position can still be reduced/closed while halted, and a new/increasing
position genuinely cannot. `resume_trading()` also correctly clears the
real marker afterward, confirmed via a second real `is_trading_halted()`
call.
