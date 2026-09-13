# Situation 21: does the CVaR gate really fail open on garbage, and what about the exact threshold?

## Question

`vinu_infra.risk_math.cvar_exceeds()`'s docstring claims it fails open
(returns `False`, "no usable signal", not "block the trade") for
non-finite or unparseable input, and explicitly calls out that
`float('nan') > x` is always `False` in Python anyway, so the explicit
`math.isfinite` guard is "a second, explicit line of defense" -- implying
the guard is defensive/redundant for NaN specifically, but load-bearing for
other garbage. Worth actually running the boundary and the garbage inputs
rather than trusting the comment's reasoning.

## Where

`vinu-infra/risk_math.py::cvar_exceeds()`.

## How tested

Direct calls with the exact threshold, just over it, `nan`, `inf`, a
non-numeric string, and `None`.

## Observed

```
cvar_95=0.03, threshold=0.03 (exactly equal): exceeds = False
cvar_95=0.0300001, threshold=0.03 (just over): exceeds = True
cvar_95=float('nan'), threshold=0.03: exceeds = False
cvar_95=float('inf'), threshold=0.03: exceeds = False
cvar_95='not-a-number' (string garbage), threshold=0.03: exceeds = False
cvar_95=None, threshold=0.03: exceeds = False
```

## Verdict: matches the documented design

The boundary is exclusive (`>`, not `>=`) -- a CVaR exactly at the
threshold does not trip the gate, only strictly worse than it does.
Every garbage input tested (`nan`, `inf`, a non-numeric string, `None`)
fails open as documented, including `inf`, which isn't actually NaN and
so isn't covered by the docstring's "`float('nan') > x` is always False
anyway" reasoning -- confirming the explicit `math.isfinite` check is
doing real, non-redundant work for that case (an unguarded `cur > thr`
with `cur = inf` would otherwise return `True`, wrongly treating an
obviously-broken computation as "definitely exceeds the risk limit").
