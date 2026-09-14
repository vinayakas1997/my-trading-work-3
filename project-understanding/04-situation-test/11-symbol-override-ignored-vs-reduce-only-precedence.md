# Situation 11: does IGNORED really block even reduce_only, unlike REDUCE_ONLY?

## Question

`OrderGuard._check_symbol_override()` has three override states:
`IGNORED`, `UNTRADEABLE`, and `REDUCE_ONLY`. The `REDUCE_ONLY` branch has an
explicit `and not reduce_only` condition (only blocks orders that aren't
already reduce_only). `IGNORED` and `UNTRADEABLE` have no such condition --
they read as unconditional blocks. Given how consistently `reduce_only` is
exempted everywhere else in this file, is that actually intentional for
`IGNORED` (e.g. "this symbol is delisted/broken, don't touch it AT ALL,
not even to close a position"), or did it just get missed the same way the
short-selling check did in situation 15?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard._check_symbol_override()`.

## How tested

Real `SymbolOverrideStore` (temp SQLite file), real `.set()` calls, real
`OrderGuard.check()`.

```python
store.set("AAPL", OverrideState.IGNORED, reason="delisted", set_by="ops")
guard.check("AAPL", "sell", qty=1, price=100.0, reduce_only=True)

store2.set("MSFT", OverrideState.REDUCE_ONLY, reason="risk review", set_by="ops")
guard2.check("MSFT", "sell", qty=1, price=100.0, reduce_only=True)  # should pass
guard2.check("MSFT", "buy", qty=1, price=100.0)                      # should still block
```

## Observed

```
IGNORED override + REDUCE-ONLY sell: allowed=False,
    reason='AAPL is IGNORED by operator override (set by ops): delisted'
REDUCE_ONLY override + REDUCE-ONLY sell: allowed=True
REDUCE_ONLY override + NEW buy: allowed=False,
    reason='MSFT is REDUCE-ONLY by operator override (set by ops):
    risk review -- only risk-reducing orders are allowed'
```

## Verdict: matches the design, and it's the right design (not situation-15's bug)

Unlike situation 15's short-check, this one holds up under scrutiny:
`IGNORED` reads (per `guard_codes.py`'s naming) as "don't act on this
symbol at all, for any reason" -- a stronger statement than `REDUCE_ONLY`'s
"only de-risking allowed." An operator who marks a symbol `IGNORED` (e.g.
data feed for it is known-bad, or it's under some kind of investigation)
plausibly wants *no* automated order touching it, including an automated
exit -- that's a decision an operator can always override by switching the
state to `REDUCE_ONLY` explicitly if they do want exits to proceed. Worth
recording specifically because it looked, on first read, like the same
"missing reduce_only exemption" pattern as situation 15 -- testing it
confirmed the two are actually different in an important way, not the same
bug in two places.
