# Situation 31: does polling a healthy position enough times eventually halt it?

## Question

`vinu-portfolio`'s `compute_risk_budget()` feeds each open position's
CURRENT `unrealized_pl` into `DailyPositionTracker.record_daily_pnl()`,
which is a `+=` accumulator. `OrderGuard._check_risk_budget()` calls
`GET /portfolio/risk/status` (which runs this pipeline) on essentially
every non-`reduce_only` order, and a monitoring dashboard would poll it
too. If a position's unrealized P&L is a live, repeatable STATE snapshot
(not a one-time event), what happens the second, third, tenth time the
exact same, completely unchanged position gets read?

## Where

`vinu-portfolio/vinu_portfolio/risk_budget.py::DailyPositionTracker.record_daily_pnl()`
+ `compute_risk_budget()`'s call site + `PortfolioService.compute_risk_status()`
(`self._risk_tracker`, constructed once in `__init__` and reused for the
service's lifetime — confirmed via `vinu-portfolio/service.py:83`'s own
comment, from an earlier "Stage 2 (how-to-make-it-live.md #22)" fix).

## How tested

Real `compute_risk_budget()`, a real `DailyPositionTracker`, a single
position held at a steady, unchanged `unrealized_pl=-500.0` (0.5% of a
$100,000 equity — nowhere near any of the -1%/-2%/-3% warning/reduce/halt
thresholds), called 5 times in a row with identical input.

```python
tracker = DailyPositionTracker()
for i in range(5):
    budget = compute_risk_budget([{"symbol": "AAPL", "unrealized_pl": -500.0}], 100_000.0, tracker=tracker)
```

## Observed (before the fix)

```
call 1: real unrealized_pl=-500 (unchanged) -> tracked daily_pnl=-500.0,  tier=0, halted=False
call 2: real unrealized_pl=-500 (unchanged) -> tracked daily_pnl=-1000.0, tier=1, halted=False
call 3: real unrealized_pl=-500 (unchanged) -> tracked daily_pnl=-1500.0, tier=1, halted=False
call 4: real unrealized_pl=-500 (unchanged) -> tracked daily_pnl=-2000.0, tier=2, halted=False
call 5: real unrealized_pl=-500 (unchanged) -> tracked daily_pnl=-2500.0, tier=2, halted=False
```

A position that never actually got any worse would have hit `TIER_HALT`
by the 6th or 7th read, purely from being observed repeatedly. There was
even an existing test,
`tests/test_risk_budget.py::TestComputeRiskStatus::test_daily_pnl_accumulates_across_repeated_calls`,
that explicitly asserted this as the intended behavior
(`second["symbols"][0]["daily_pnl"] == 1000.0` for two identical
`unrealized_pl=500.0` reads) — this wasn't an oversight, it was a
previous "Stage 2" fix that moved the tracker onto the service instance
specifically *so that* repeated calls would accumulate, on the mistaken
premise that "accumulate across calls" was the only way to avoid losing
track of how bad a position got earlier in the day.

## Verdict: real, severe bug, fixed

This makes `OrderGuard`'s `RISK_BUDGET_HALT` gate actively dangerous
rather than merely unreliable: a symbol traded (and therefore risk-
checked) more often during the day becomes artificially *more* likely to
get spuriously halted than an identical position that's simply checked
less, with zero relationship to real performance. `record_daily_pnl`'s
`+=` semantics are correct for a genuinely discrete, one-time REALIZED
P&L event (its own direct unit tests, accumulating `+100` then `-50` into
`50`, are fine and untouched) — the bug was specifically in feeding it a
repeatable *state* snapshot (`unrealized_pl`) as if every read were a new
event.

**Fixed**: added `DailyPositionTracker.record_unrealized_pnl()`, which
tracks the WORST (most negative) unrealized reading seen for a symbol
today — sticky/latching, the same way a real circuit breaker behaves (a
position that touched -3% and later recovered to -1% should stay
flagged, not silently clear), but immune to reading the same live value
any number of times. `compute_risk_budget()` now calls this instead of
`record_daily_pnl()` for the unrealized-P&L path; `record_daily_pnl()`
itself is untouched and stays available for a future genuine
realized-P&L-event feed (none exists in this codebase yet).

Re-verified: 5 identical reads now report an unchanged `tier=0` the whole
way through; a position that dips to `-3500` (breaching `TIER_HALT`) and
later recovers to `-50` correctly stays `halted=True` with `daily_pnl`
latched at `-3500`. Replaced the test that codified the bug with two
correct ones in `tests/test_risk_budget.py::TestComputeRiskStatus`
(steady polling doesn't inflate; a breach latches through a recovery).
Full `test_risk_budget.py` (25 passed) and full `vinu-portfolio` suite
(169 passed; the only 2 failures, in `test_auth.py`, confirmed pre-existing
and unrelated via `git stash`) both pass.

This is arguably the most severe finding in the whole audit precisely
because of who relies on it: `OrderGuard._check_risk_budget()` treats a
`TIER_HALT` result as an unconditional hard reject for every non-
`reduce_only` order, with no way for a caller to know the number was
corrupted by polling frequency rather than real risk.
