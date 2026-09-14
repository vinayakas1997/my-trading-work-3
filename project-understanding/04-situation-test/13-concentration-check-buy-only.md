# Situation 13: does the concentration check really skip sell orders entirely?

## Question

`_check_portfolio_concentration()` starts with `if side != "buy": return
GuardResult(True)`, with a comment explaining a sell reduces exposure so
blocking it on concentration grounds would be "actively harmful, not
protective." Does a sell order for an already-over-the-cap symbol really
skip the check completely -- not just pass it, but never even make the
`/portfolio/state` network call?

## Where

`vinu-agent/vinu_agent/broker/order_guard.py::OrderGuard._check_portfolio_concentration()`.

## How tested

Real `OrderGuard.check()`, `requests.get` patched with a call-counting stub
returning a portfolio where AAPL is already at 90% target weight against a
10% `max_symbol_concentration_pct` cap. Ran a buy (expected to be blocked
and to trigger the call) then a sell for the same symbol (expected to skip
the check and the call).

## Observed

```
BUY into 90%-concentrated symbol (cap 10%): allowed=False,
    reason="AAPL already accounts for 90.0% of the portfolio's target
    weight, exceeding max_symbol_concentration_pct 10% -- vinu-portfolio
    and execution may have drifted out of sync."
/portfolio/state calls after the buy attempt: 1
SELL of the same over-concentrated symbol: allowed=False
/portfolio/state calls after the sell attempt (should be unchanged): 1
```

(The sell's own `allowed=False` here is from a *different*, expected
check -- `allow_short` defaults to `False` and this sell wasn't marked
`reduce_only`, so it correctly hits situation 15's short-selling check
instead. The concentration check itself was never reached, confirmed by
the call count staying at 1.)

## Verdict: matches the documented design

The `side != "buy"` short-circuit is real -- zero additional network calls
for the sell, confirming the concentration check is skipped outright, not
just evaluated-and-passed. Worth noting this test incidentally re-confirms
situation 15's fix is scoped correctly: a genuinely short-selling sell (not
`reduce_only`) is still and should still be blocked by that other check.
