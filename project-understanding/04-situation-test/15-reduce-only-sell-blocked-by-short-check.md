# Situation 15: under the mandate's own default, can a position ever be exited?

## Question

While building a batch of OrderGuard scenarios (situations 5-14), one of
them -- "an unpriceable order is rejected for a normal order but allowed
through for `reduce_only`" -- unexpectedly came back `allowed=False` for the
`reduce_only` case too. Chasing why, one line at a time, surfaced a real
question worth testing in isolation: `OrderGuard.check()` repeatedly
documents "reduce_only is always exempt" for the kill switch, mandate
consent expiry, the portfolio-wide daily order cap, and the risk-budget
halt tier -- each with its own comment saying so. Does the short-selling
check follow the same rule?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`side == "sell" and not mandate.allow_short` check (originally line 246-247,
right after the ticker allow/block checks).

## How tested

Real `OrderGuard.check()`, real `TradingMandate`, only the broker mocked
(`get_account`/`get_clock` never even get called for this path). Isolated
from every other check by setting `max_position_pct=1.0` etc. so nothing
else in the method could produce a `False` result first.

```python
mandate = TradingMandate(require_active_artifact=False, require_market_open=False,
                          allow_short=False,  # the actual repo default
                          max_position_pct=1.0, max_capital_utilization_pct=1.0)
guard = OrderGuard(mandate=mandate, broker=MagicMock(), daily_limit_store=...)
guard.check("AAPL", "sell", qty=1, price=100.0, reduce_only=True)
```

## Observed

```
allow_short=False (the repo default), REDUCE-ONLY sell (closing a long):
    allowed=False
    reason='Short selling is not permitted by mandate'
    code=ReasonCode.SHORT_NOT_PERMITTED

allow_short=True, identical REDUCE-ONLY sell:
    allowed=True
```

Confirmed this is reachable from a real order, not just a theoretical
`check()` call: `trade_tool.py`'s `execute()` takes `side` and
`reduce_only` as independent kwargs from the caller (line 106 reads
`reduce_only = bool(kwargs.get("reduce_only", False))`, `side` comes
straight from the tool call) and passes both straight through to
`guard.pre_approve(symbol, side, qty, reduce_only=reduce_only)` (line 359)
-- so `submit_order(symbol="AAPL", side="sell", qty=..., reduce_only=True)`,
the documented way to close or trim a long position, hits this exact check.

## Verdict: real bug, fixed

A `reduce_only` sell can only ever mean "close or trim an existing long" --
reducing a short position is a `reduce_only` **buy** (buying back borrowed
shares), never a sell. So there is no scenario where `side == "sell" and
reduce_only` should ever be short-selling, and this check had no reason to
fire for it. Under the mandate's own default (`allow_short: bool = False`),
a position opened through a normal buy became permanently un-exitable
through `submit_order`'s own `reduce_only` mechanism -- exactly the
"trapped position" failure mode the kill-switch's `reduce_only` exemption
(a few lines above this check, in the same method) was explicitly written
to prevent for the halted case. This one check just didn't get the same
treatment.

**Fixed**: `vinu-agent/vinu_agent/broker/order_guard.py` --
`if side == "sell" and not reduce_only and not mandate.allow_short:` (was
missing `and not reduce_only`). Three new tests added to
`tests/test_order_guard.py::TestShortCheckExemptsReduceOnly` covering: a
reduce_only sell is allowed under `allow_short=False`; a non-reduce_only
sell is still correctly blocked under the same mandate (this check still
does its job for actual shorting attempts); and a reduce_only sell is
(still) allowed when `allow_short=True`. Full `test_order_guard.py` suite
re-run: 71 passed, only the same 2 pre-existing, unrelated
`TestOrderThrottle` timing failures already confirmed via `git stash`
elsewhere in this audit.
