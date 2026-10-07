# Situation 22: do the ticker allow/block-list checks trap an existing position too?

## Question

Chasing situation 19 (a corrupted mandate falling back to an empty
`allowed_tickers`) raised a sharper question: does `OrderGuard.check()`'s
`allowed_tickers`/`blocked_tickers` logic exempt `reduce_only` orders at
all, the way the kill switch, mandate-expiry, portfolio-wide daily cap, and
(since situation 15) the short-selling check all do? If not, a symbol
falling out of an allowlist -- or the allowlist collapsing to empty, as in
situation 19's fail-closed fix -- would trap any existing position in it
with no way to exit via `submit_order`.

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard.check()`, the
`blocked_tickers` and `allowed_tickers` checks (right after the ticker
override/consent checks, before the short-selling check).

## How tested

Real `OrderGuard.check()`, two separate mandates: one with `AAPL` in
`blocked_tickers`, one with `allowed_tickers={"MSFT"}` (AAPL excluded).
Ran a `reduce_only` sell for AAPL against each.

```python
guard(blocked_tickers={"AAPL"}).check("AAPL", "sell", qty=1, price=100.0, reduce_only=True)
guard(allowed_tickers={"MSFT"}).check("AAPL", "sell", qty=1, price=100.0, reduce_only=True)
guard(allowed_tickers={"MSFT"}).check("AAPL", "buy", qty=1, price=100.0, reduce_only=True)  # closing a short
```

## Observed (before the fix)

```
AAPL is blocked, REDUCE-ONLY sell (closing a position): False | AAPL is in the blocked tickers list
AAPL not in allowlist, REDUCE-ONLY sell: False | AAPL is not in the allowed tickers list
AAPL not in allowlist, REDUCE-ONLY buy (closing a short): False | AAPL is not in the allowed tickers list
```

Neither check exempted `reduce_only` at all -- same missing-exemption
pattern as situation 15, in two more places.

## Verdict: mixed -- one is a real bug (fixed), one is correct as-is

These two checks aren't actually the same kind of restriction, and testing
both side by side made that clear:

- **`blocked_tickers`** is a deliberate "don't touch this symbol for any
  reason" list -- the same semantics as the symbol-override `IGNORED`
  state, which situation 11 already confirmed is *correctly* not exempted
  for `reduce_only` (an operator blocking a symbol, e.g. for a compliance
  concern, plausibly wants no automated order of any kind touching it).
  **Left unchanged.**
- **`allowed_tickers`** is a scope restriction on what may be *opened*, not
  a "this symbol is untouchable" statement. A symbol can fall out of an
  allowlist (a strategy retired, an operator narrowing scope, or -- per
  situation 19 -- a corrupted mandate file failing closed) while a
  position from when it *was* allowed is still open. There's no reason an
  exit should be blocked by a list that only ever governed what could be
  newly opened. **Fixed**: `order_guard.py` now reads
  `if not reduce_only and "*" not in mandate.allowed_tickers and symbol
  not in mandate.allowed_tickers:` (was missing `not reduce_only`).

Verified after the fix: a `reduce_only` sell for a symbol outside the
allowlist now clears (`allowed=True`); a normal buy for the same symbol
still correctly blocks (`TICKER_NOT_ALLOWED`); and `blocked_tickers` still
blocks a `reduce_only` exit exactly as before (confirmed intentional, not
touched). Three new tests added to
`tests/test_order_guard.py::TestTickerAllowlistExemptsReduceOnlyButBlockedTickersDoesNot`.
Full `test_order_guard.py` suite: 71 passed (2 pre-existing, unrelated
`TestOrderThrottle` failures).

This fix is also what makes situation 19's fail-closed fallback
(`allowed_tickers=set()` on a corrupted mandate) safe rather than another
trap: without it, a broken mandate file would have blocked every exit too,
not just new orders.
