---
name: e2e-portfolio-strategy-verification
status: definition-phase
---

# Step 4 — `vinu-strategy` and `vinu-portfolio` Verification

## Why this file exists

Flagged as a real gap after the first pass of this folder: `02` and `03`
verify that `vinu-research` generated and promoted a strategy artifact, but
never confirm that artifact is actually visible where it's supposed to be
read from afterward — `vinu-strategy`'s own routes, and `vinu-portfolio`'s
aggregation on top of those. A "completed" research run means nothing to
the rest of the system if nothing downstream can see it.

## Explicitly deferred, not in scope for this pass

**The live broker connection** (`vinu-live`'s real Alpaca order-execution
path, and any `vinu-portfolio`/`vinu-agent` route that depends on a real
live-money broker session) — check later, separately. Everything below
verifies against **replay-mode data** (the `HistoricalFillBroker`, driven by
`vinu-agent/scripts/run_month_replay.py` in `05`), not a live Alpaca
connection. Where a route's output depends on which broker is behind it,
that's called out explicitly so it isn't silently assumed to mean "live
trading verified."

## 1. `vinu-strategy` (port 8084) — confirm the promoted artifact is visible

```bash
curl -s http://localhost:8084/strategy/strategies
curl -s "http://localhost:8084/strategy/strategies/{name}"
curl -s http://localhost:8084/strategy/weights
curl -s http://localhost:8084/strategy/runs
```

Use the strategy name confirmed via `vinu-research`'s `/research/artifacts`
in `03`. Confirm the same artifact appears here — same name, same symbol —
not just that `vinu-research` says it exists. If `vinu-strategy` and
`vinu-research` turn out not to share storage the way this assumes, that
mismatch is exactly the kind of thing this file exists to catch; document
it rather than assuming one implies the other.

### Document

- Confirmed (or not) that each of the 3 tickers' promoted artifacts appear
  in `/strategy/strategies` and `/strategy/weights`.
- Whether `/strategy/runs` reflects the same run IDs seen in
  `/research/runs`, or a separate numbering — note which, don't assume.

## 2. `vinu-portfolio` (port 8090) — confirm aggregation actually aggregates

```bash
curl -s http://localhost:8090/portfolio/strategies
curl -s http://localhost:8090/portfolio/weights
curl -s http://localhost:8090/portfolio/daily-allocation
curl -s http://localhost:8090/portfolio/daily-game-plan
curl -s http://localhost:8090/portfolio/state
curl -s http://localhost:8090/portfolio/risk/status
```

**Dependency to know before reading these**: `/portfolio/state` and
`/portfolio/risk/status` both call `vinu-agent`'s `GET
/agent/broker/positions` internally (`vinu_portfolio/service.py:545-552`)
to compute risk budget and current exposure. In replay mode this resolves
through `HistoricalFillBroker`, not a real Alpaca account — confirm the
call succeeds and returns *some* position state (even if empty/flat) for
the replay session, not that it reflects real money. That's the boundary
of what this pass verifies; a real live-Alpaca `/portfolio/state` read is
part of the deferred live-broker check above, not this one.

`/portfolio/strategies`, `/portfolio/weights`, and `/portfolio/daily-
allocation`/`/portfolio/daily-game-plan` should reflect the same 3
promoted artifacts confirmed in step 1 — if any of the 3 tickers' artifacts
are missing here, that's a real aggregation gap to document, not a
different kind of "the data isn't ready yet" situation (all the upstream
data has already been confirmed present by this point in the checklist).

### Document

- Whether all 3 tickers' strategies appear in `/portfolio/strategies` and
  `/portfolio/weights`.
- `/portfolio/state`'s reported positions during the replay window (expect
  this to change as `05`'s replay session runs, not to be static) —
  confirm it's actually reading live replay state, not a cached/stale
  snapshot.
- `/portfolio/risk/status`'s reported exposure/budget numbers — sanity
  check these aren't all zero/null, which would indicate the positions
  call silently failed rather than genuinely returning "no positions."

## What to confirm before moving to `05`

- [ ] All 3 tickers' promoted strategy artifacts visible in
      `vinu-strategy`'s own routes, not just `vinu-research`'s
- [ ] `vinu-portfolio`'s aggregation routes reflect the same 3 artifacts
- [ ] `/portfolio/state`/`/portfolio/risk/status` return real (non-error)
      output against the replay broker — confirmed as a replay-mode check,
      explicitly not a live-broker one
