# Situation 28: does a real limit order actually survive its own pre-submission re-check?

## Question

Chasing the "market order into a never-held symbol should fail closed"
question (the A36 fix's stated intent) with a *real* `OrderGuard` end to
end, through the real `TradeTool.execute()`, turned up something bigger
than the thing being tested: does a real limit order -- or a real market
order into an *already-held* symbol, both of which price themselves via
`estimated_value` rather than a bare `qty*price` -- actually survive all
the way to submission through the genuine production code path?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.pre_approve()` +
its one real call site,
`vinu-agent/vinu_agent/tools/trade_tool.py::TradeTool.execute()` (the
`guard.pre_approve(symbol, side, qty, reduce_only=reduce_only)` line,
immediately before the actual broker submission).

## How tested

Real `TradeTool.execute()`, a real `OrderGuard` instance (not the
`guard.pre_approve.return_value = GuardResult(True)` every single other
`TradeTool` test in this repo uses) -- only the broker's HTTP boundary
mocked. A real limit order (`qty=5, limit_price=100.0`), which
`execute()` itself correctly computes `estimated_value=500.0` for and
passes to the *first* `guard.check()` call.

```python
result = tool.execute(symbol="NVDA", qty=5, side="buy", order_type="limit", limit_price=100.0)
```

To see exactly what was happening, a spy wrapped `guard.check` and
printed every call:

```
guard.check called with args=('NVDA','buy',5.0) kwargs={'price':100.0,'estimated_value':500.0,'reduce_only':False}
guard.check called with args=('NVDA','buy',5.0,None) kwargs={'reduce_only':False}
```

Two calls. The first is the intended gate, correctly priced, and
approves. The second -- called from *inside* `pre_approve()`, the
"fresh re-check right before submission" the kill-switch race fix
deliberately added -- passes `price=None` and no `estimated_value` at
all, because `pre_approve()`'s signature never had an `estimated_value`
parameter, and `trade_tool.py`'s call to it
(`guard.pre_approve(symbol, side, qty, reduce_only=reduce_only)`) never
even passed `price`.

## Observed (before the fix)

```json
{
  "status": "rejected",
  "symbol": "NVDA",
  "side": "buy",
  "qty": 5.0,
  "reason": "Cannot determine order value -- no usable price or estimated_value. ...",
  "reason_code": "order_value_unknown"
}
```

A limit order that had just been correctly approved, priced, and
notionally-capped moments earlier was silently re-rejected right before
submission, because the second internal check recomputed `value` as `0`
with no price information at all. The same happens for any market order
into an *already-held* symbol (the A36 fix's own reference-price path) --
its `estimated_value` also never reaches `pre_approve()`. Only orders
that price purely via a bare `qty*price` matching exactly what
`pre_approve()` was separately given -- which, since `trade_tool.py`
never passes `price` to it either, is *no real call site at all* --
would have escaped this.

## Verdict: real, severe bug, fixed

This is the most consequential finding in this audit: in the real,
unmocked, end-to-end path, essentially no properly-priced non-reduce_only
order could ever clear the pre-submission re-check, because the
information needed to price it was silently dropped one call earlier.
It went uncaught by the entire existing test suite because *every* test
of a successful submission -- in `test_trade_tool.py`,
`test_trade_tool_audit_trail.py`, and every situation script in this
folder up to this point -- mocks `guard.pre_approve.return_value =
GuardResult(True)` directly, never letting the real method's own internal
`self.check(...)` call run with real arguments. `reduce_only` orders were
unaffected (they don't need a real value at all), which is exactly why
this stayed invisible: every OTHER situation in this audit that exercised
a real, successful submission end-to-end (situation 4) also happened to
mock `pre_approve` directly rather than using a live `OrderGuard`.

**Fixed**: `pre_approve()` now accepts `estimated_value` and forwards both
it and `price` to its internal `self.check(...)` call, and also uses
`max(estimated_value or 0.0, qty*(price or 0.0))` (matching `check()`'s
own rule) when recording the order's value for daily-volume tracking,
instead of the old bare `qty*(price or 0.0)` which would have undercounted
the exact same class of order. `trade_tool.py`'s call site now passes
`price=(limit_price or None), estimated_value=estimated_value` --
mirroring the first `guard.check()` call exactly.

Re-ran the failing scenario after the fix: the limit order submits
correctly, and the already-held-symbol market order does too. Confirmed
the *intended* rejection (a brand-new symbol, no limit price, no held
position -- genuinely unpriceable) still correctly fails closed, unchanged.
Added 5 new tests: `tests/test_order_guard.py::TestPreApproveForwardsEstimatedValue`
(3 tests on `pre_approve()` directly -- estimated_value accepted, still
enforces the cap, records the correct daily volume) and
`TestTradeToolPreApproveEndToEndWithARealOrderGuard` (2 tests driving the
real production call site with a real `OrderGuard`, the way every other
existing test in the suite does not). Verified all 5 new tests actually
fail against the pre-fix code (via `git stash`) before confirming they
pass against the fix -- a genuine regression test, not just a test that
happens to pass. Full `test_order_guard.py` (124 passed, same 2
pre-existing unrelated `TestOrderThrottle` failures), `test_trade_tool.py`,
`test_mandate_load_fallback.py`, and `test_kill_switch.py` suites all
still pass.

This is the single clearest demonstration in this whole exercise of why
the auditor's rule -- "actually exercise the real modules... not a mock of
the thing being tested" -- matters: every layer of unit testing here was
individually green, and the bug still made it all the way to what would
have been a production incident on the very first real limit order.
