# Pending: expose the Phase 1 manifest over HTTP

**Priority: high.**
**Status: not started -- planning only, do not implement yet without a
proper look first.**

## What exists already

`vinu_infra.system_manifest.build_manifest(angles)` is a real, tested,
working function (Decision 6/7 of `01-planning.md`) -- it takes a
discovered angle list and returns the full report: angle inventory by
category, current model policy + version, active angle count, recording
time-format in effect, and the evidence-table column count. It has zero
open bugs. **The gap is purely that nothing calls it over HTTP** -- it's
only reachable from Python code that already has an `AngleRunner`
instance in hand.

## Why this needs actual planning, not just "add a route"

- **Which service owns this route?** `build_manifest()` needs an angle
  list, which only `vinu-initial-analysis`'s `AngleRunner` currently
  produces (`list_angles()`). That's the obvious home. But the manifest
  is conceptually a `vinu-infra`-level, cross-component concept (Decision
  4/6 explicitly put the model policy there because it's shared beyond
  just this one component) -- so should other components (`vinu-live`,
  `vinu-research`) that also care about "is MODELS on right now" get
  their own copy of this route, or is `vinu-initial-analysis`'s the one
  and only place to ask, with everyone else calling out to it? This
  needs a real decision, not a default.
- **Auth.** Every other route in `routes_read.py` is presumably behind
  whatever auth the rest of `vinu-initial-analysis` uses -- confirm the
  manifest doesn't need anything stricter (it reveals model policy
  state, not sensitive trading data, but "is this fine to expose the
  same way as /analysis/story" is worth a real check, not an assumption).
- **Staleness/caching.** `build_manifest()` is cheap today (pure
  computation over an already-in-memory angle list), but if a future
  caller expects to poll it frequently, is there a need for any
  caching, or is "always live" the right answer permanently? Probably
  the latter (nothing about this changes fast), but worth stating
  explicitly rather than assuming.
- **Response shape stability.** Once this is a real HTTP contract,
  changing `build_manifest()`'s return shape becomes a breaking change
  for whoever's consuming the route. Worth deciding whether to version
  the response or just accept "this is internal tooling, shape can move"
  before locking it in.

## Suggested next step (not started)

Settle the four questions above as short decisions (same format as
`01-planning.md`'s numbered entries), THEN add the route -- likely
`GET /analysis/manifest` in `vinu-initial-analysis/vinu_initial_analysis/
server/routes_read.py`, following the exact same pattern
`GET /analysis/coverage/{ticker}` already uses (thin route function,
`svc.list_angles()` for the angle list, delegate everything else to the
existing tested function).
