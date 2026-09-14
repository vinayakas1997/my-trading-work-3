# Situation 12: does the order throttle's sliding window actually slide?

## Question

`OrderGuard`'s in-process order throttle (B20) is a `deque` of monotonic
timestamps, pruned lazily on each `check()` call: entries older than
`VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC` get dropped before the count is
checked against `VINU_AGENT_ORDER_THROTTLE_PER_SEC`. Does a real burst
past the limit actually get throttled, and does it actually recover once
real wall-clock time moves the window forward -- using real
`time.monotonic()`, not a mocked clock?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the B20
throttle block (`self._throttle_window`).

## How tested

Real `OrderGuard`, `VINU_AGENT_ORDER_THROTTLE_PER_SEC=10`,
`VINU_AGENT_ORDER_THROTTLE_WINDOW_SEC=0.3`. Ten `check()` calls back to
back (should all pass), an 11th immediately after (should trip), then a
real `time.sleep(0.35)` (past the 0.3s window) and a 12th call (should
pass again).

One real methodology snag worth recording on its own: the first attempt at
this test left `requests.get` unmocked, and a real DNS-resolution-failure
round trip per `check()` call (to a deliberately fake portfolio host) took
long enough that the "instant burst" of 10 calls was no longer actually
instant relative to the 0.3s window -- entries were getting pruned
mid-burst from real, unintended network latency, and the throttle never
tripped. Patching `requests.get` to fail in-memory (no real I/O) fixed the
test itself; this wasn't a bug in `OrderGuard`, but it's a good reminder
that "real code, not mocks of the thing under test" still requires mocking
the actual external I/O boundary, or the *test's own* incidental latency
becomes a confound.

## Observed

```
orders 1-10 (instant burst): all allowed = True
order 11 (still within 0.3s window): allowed=False,
    reason='Order throttle: 10 orders / 0.3s limit exceeded'
order 12 (after real 0.35s sleep, window=0.3s): allowed=True
```

## Verdict: matches the documented design

The sliding window genuinely slides -- confirmed with a real clock, not a
frozen or mocked one, so the lazy-pruning logic in `check()` is doing real
work rather than happening to look correct by inspection.
