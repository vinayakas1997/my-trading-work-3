---
name: phase-4-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 4 -- NOT a new build. Fixing the one broken endpoint that keeps vinu-live's already-real ShadowEvaluator from working, per the consolidation-plan finding that Live+Shadow already exists.
---

# Phase 4 -- Live + Shadow (fix, not build)

## Correction to the original mermaid-doc framing

`mermaid-explanation.md` originally marked the `LS` ("Live + Shadow")
node `<i>new</i>`. That's wrong, confirmed by reading `vinu-live` directly
(see `component-consolidation-plan.md`, Group 2 section): `vinu-live/
shadow_evaluator.py`'s `ShadowEvaluator` already compares a `BENCHING`
artifact's paper-trading Sharpe against its backtest Sharpe and
auto-promotes to `ACTIVE` if the degradation is within tolerance -- its
own docstring calls this "the paper-trading phase becomes an automated
gate." It's real, it's written, and it's currently broken for one
specific reason.

## What's actually broken

`ShadowEvaluator._fetch_paper_sharpe` calls
`/agent/broker/performance/{artifact_id}` on `agent-api`. That route does
not exist in `vinu_agent/server/routes_broker.py` -- confirmed by reading
the file directly this session (it has `/broker/halt`, `/broker/resume`,
`/broker/status`, `/broker/account`, but nothing under `/broker/
performance/`). Every call 404s today, silently disabling the auto-
promotion gate.

## What Phase 4 builds

**One new route: `GET /agent/broker/performance/{artifact_id}`** in
`vinu_agent/server/routes_broker.py`, returning the real paper-trading
Sharpe (and whatever else `ShadowEvaluator` actually reads off the
response -- confirm the exact expected response shape from
`shadow_evaluator.py`'s own parsing code before writing the route, don't
guess the shape from the endpoint name alone).

**Where the data probably lives:** `routes_broker.py` already imports
`from ..broker.performance_store import get_store` for the existing
`/broker/account` endpoint. That module is the most likely real source
for the fills/equity-curve data needed to compute a per-artifact Sharpe --
**confirm `performance_store.py`'s actual schema and query API before
implementing**, this plan hasn't read that file directly this session.

## Open question this phase must resolve before implementing, not after

**Where does `BENCHING` -> `ShadowEvaluator` fit relative to Phase 2's
`PEND`/`PENDBLOCK` states?** Two real possibilities, not yet distinguished
this session:
- `BENCHING` happens *before* `risk_gatekeeper` -- i.e. Researcher/
  Executor's role d (paper-trade rehearsal) sets `BENCHING`, and
  `ShadowEvaluator`'s auto-promotion is effectively what produces the
  evidence `risk_gatekeeper` later reviews.
- `BENCHING` happens *after* `capital_allocator` funds a candidate --
  a live paper-shadow period post-funding, pre-full-`ACTIVE`, meaning
  `ShadowEvaluator`'s auto-promotion would need to interact directly with
  Phase 2/3's `PEND`/`PENDBLOCK` machinery.

These lead to genuinely different wiring. **Read `vinu-live`'s real
callers of `BENCHING` and cross-reference against `SqliteStrategyStore`'s
actual status-transition rules before writing any code for this phase** --
don't assume either answer. This is exactly the kind of thing this
project has repeatedly gotten wrong by guessing instead of checking (the
original indicators-column bug, the "new" mislabel on this very node).
