# Expose the Phase 1 manifest over HTTP

**Priority: high.**
**Status: done (2026-09-24) -- `GET /analysis/manifest` live in
`vinu-initial-analysis`. See "What was built" at the end of this file.**

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

## What was built (2026-09-24)

The four open questions were settled as **Decision 13** in
`01-planning.md` — short version: `vinu-initial-analysis` owns the route
(the only place it's exposed; other services call out to it rather than
each getting a copy, same reasoning as Decision 9), no auth beyond what
the file's other routes already have (none), no caching (always live),
unversioned (same posture as every other route here). All four turned
out to already have an established answer elsewhere in this same
codebase once actually checked — no genuinely new architectural call
needed.

**Route**: `GET /analysis/manifest` in
`vinu-initial-analysis/vinu_initial_analysis/server/routes_read.py`,
exactly the suggested shape — a thin function calling
`build_manifest(svc.list_angles())` directly, no new logic.

**Verified against a real running app** (not just unit-tested in
isolation): a real `TestClient` request against `/analysis/manifest`
returns the genuine current state — 29 angles discovered (including
`signal_evidence`, angle #29), 26 active under the default policy,
`policy_version`/`evidence_table` populated correctly.

**Tests** (`vinu-initial-analysis/tests/test_manifest_route.py`, 3
tests, all passing):
- The response has the real `build_manifest()` shape.
- The route's response is byte-for-byte identical to calling
  `build_manifest(service.list_angles())` directly (not just "returns
  some keys").
- `build_manifest()` is genuinely invoked fresh on every request (proven
  by mocking it and asserting call count == number of requests) --
  confirms the "no caching" decision holds structurally, not just by
  claim. (`MODELS_ENABLED` itself is intentionally boot-only per
  `model_policy.py`'s own docstring -- a module-level constant read once
  at import -- so this test deliberately doesn't try to prove the policy
  flag is live-editable within a running process, since Decision 4
  explicitly says it shouldn't be.)

**Side effect of doing this properly**: this sandbox was also missing
`cachetools` (declared dependency, `vinu-initial-analysis/pyproject.toml`
line 21: `cachetools>=5.3`), which had been silently blocking
`test_ticker_coverage_route.py` before this change (same class of gap as
`tenacity` in `05-pending-signal-evidence-tool-call.md`). Installed it
and re-ran that file for real: 3/3 passed. Broader regression across
`vinu-initial-analysis` (excluding the already-known `torch`/
`statsmodels`-dependent files, unrelated to this route): 286 passed, 22
pre-existing failures independently confirmed unrelated (missing
`statsmodels`/`torch`, plus the previously-confirmed pre-existing SQLite
temp-file lock issue on Windows), no new regressions.
