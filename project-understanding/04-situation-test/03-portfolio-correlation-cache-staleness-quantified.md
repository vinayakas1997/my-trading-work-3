# Situation 3: how stale can the correlation matrix OrderGuard reads actually get?

## Question

The earlier audit (`research-discussion-v2/fixes-log.md`, item #18) reviewed
vinu-portfolio's 60s `_portfolio_cache` and concluded, on paper, that it was
an acceptable trade-off since the cache key is the *set* of active
strategies, not market data. But that's a reasoned argument, not a
measurement — how stale can the actual correlation numbers get in a
concrete, real scenario where the strategy set stays fixed but the market
genuinely changes regime?

## Where

`vinu-portfolio/vinu_portfolio/service.py::build_portfolio()` (cache key =
`(name, artifact_id, is_candidate)` tuples, TTL 60s) — read by
`vinu-agent/vinu_agent/broker/order_guard.py::_check_portfolio_concentration()`
via `GET /portfolio/state`, which enforces `mandate.max_pairwise_correlation`.

## How tested

Real `PortfolioService.build_portfolio()`, `allocate_risk_parity()`, and
`robust_correlation_matrix()` — only `list_active_strategies()` (network/DB)
and `_build_returns_df()` (network/DB) were faked, returning a FIXED
two-strategy set (so the cache key never changes) but a DELIBERATELY
flipped returns series between calls: strongly positively correlated
(+0.995 target) for the first call, strongly negatively correlated (-0.994
target) for any later real computation — a large, unambiguous regime change,
not a subtle one.

```python
result1 = await svc.build_portfolio()                      # fresh
result2 = await svc.build_portfolio()                      # 0s later, same TTL window
svc._portfolio_cache[key] = (ts - 61.0, cached_result)      # force TTL expiry, no real sleep
result3 = await svc.build_portfolio()                       # after "expiry"
```

## Observed

```
Call 1 (fresh): pairwise correlation = 0.995, _build_returns_df calls so far = 1
Call 2 (0s later, same strategy set): pairwise correlation = 0.995, _build_returns_df calls so far = 1
Call 3 (after TTL expiry): pairwise correlation = -0.994, _build_returns_df calls so far = 2

Call 2 used stale (call-1) data despite a real regime flip: True
Call 3 (post-TTL) picked up the new regime: True
```

`_build_returns_df` was called exactly once across calls 1 and 2 combined —
call 2 never touched the underlying data at all, purely served the cached
result.

## Verdict: matches the documented design, now with real numbers instead of an argument

This isn't a bug — it's the cache behaving exactly as designed, and
`max_pairwise_correlation` defaults to `1.0` (disabled) so this doesn't bite
anyone at default settings. But "acceptable trade-off" was previously an
unquantified claim; now it's concrete: an operator who *has* enabled
`max_pairwise_correlation` could see two positions go from perfectly
correlated to perfectly anti-correlated and have `OrderGuard`'s
concentration check still act on the old number for up to 60 seconds. Worth
knowing precisely, especially since a real correlation regime flip of this
magnitude (not a subtle drift) is exactly the kind of event
`max_pairwise_correlation` exists to catch. Not fixed here — this is a
recorded situation, and the earlier audit's "reasonable trade-off" judgment
still holds given the check is opt-in — but any operator turning that check
on should know the real number is "up to 60s," not an abstraction.
