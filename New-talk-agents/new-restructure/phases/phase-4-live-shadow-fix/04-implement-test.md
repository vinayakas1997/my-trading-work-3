---
name: phase-4-implement-test
status: built -- Phase 4 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 4 -- Implementation record

Built 2026-08-11, directly following Phase 3 in the same session.

## The plan's central premise was already false -- and a worse bug was hiding behind it

`01-plan.md` said `GET /agent/broker/performance/{artifact_id}` didn't
exist. **It already existed, fully implemented and tested**
(`vinu_agent/server/routes_broker.py`, `tests/test_routes_broker.py`) --
confirmed by reading the file directly, not by trusting the plan or the
stale comment inside `shadow_evaluator.py` that made the same claim. That
comment, and `skills/live-safety/SKILL.md`'s Stage 2 section, were both
written at an earlier point and never updated once the endpoint actually
landed.

Building the real integration test the phase's own test plan called for
(`ShadowEvaluator`'s real HTTP call against the real endpoint, not a
mock) surfaced a genuinely worse, previously-invisible bug:
**`shadow_evaluator.py` called `await resp.json()` in two places, but
`httpx.Response.json()` is synchronous, not a coroutine.** Against a real
`httpx.AsyncClient`, this raises `TypeError`, silently caught by a broad
`except Exception`, always returning `[]`/`None`. The existing mocked
tests (`test_shadow_evaluator.py`) never caught this because their own
`MockResponse.json()` was itself declared `async def json()` -- the mock
was shaped to match the bug, not the real interface. **`ShadowEvaluator`
had never actually worked against a real server, for a different and
more fundamental reason than the one the plan named.**

## What was actually broken and fixed

1. `_list_benching_artifacts` (line ~57): `return await resp.json()` ->
   `return resp.json()`.
2. `_fetch_paper_sharpe` (line ~115): `data = await resp.json()` ->
   `data = resp.json()`.
3. The stale "endpoint doesn't exist" comment in `_fetch_paper_sharpe`
   removed.
4. `test_shadow_evaluator.py`'s `MockResponse.json()` changed from
   `async def` to a plain method, matching real `httpx.Response`.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-live/vinu_live/shadow_evaluator.py` | modified | Both `await resp.json()` call sites fixed to synchronous `resp.json()` (the real bug). Stale "endpoint doesn't exist" comment removed. |
| `vinu-components/vinu-live/tests/test_shadow_evaluator.py` | modified | `MockResponse.json()` de-asynced to match real `httpx.Response`. New `test_withholds_promotion_when_degradation_exceeds_tolerance` -- confirms the real non-promotion branch (`status="below_threshold"`, no `/promote` call at all). |
| `vinu-components/vinu-live/tests/test_shadow_evaluator_real_endpoint.py` | new | 3 tests running `ShadowEvaluator`'s real code against vinu-agent's real `routes_broker.py` FastAPI app via `httpx.ASGITransport` (in-process, no live server, but genuinely un-mocked route-handler code) -- this is what caught the sync/async bug above. Covers the literal "used to 404, now doesn't" regression case, unknown-artifact insufficient-data, and a full `evaluate_all()` promotion pass against the real endpoint. |
| `vinu-components/vinu-agent/teams/risk_gatekeeper/TEAM.md` | modified | Stale line ("APPROVED transitions to ACTIVE via mark_active()") corrected to match Phase 2's real PEND-based behavior -- found while investigating this phase's BENCHING-order question. |
| `vinu-components/vinu-agent/skills/live-safety/SKILL.md` | modified | Stage 2 section corrected: the endpoint exists and works now (proven by the new real-endpoint test), only the "nothing calls `evaluate_all()` on a schedule" gap remains. Chain-diagram label changed from `[BUILT, NEVER RUNS]` to `[WORKS, NOT SCHEDULED]`. |

## The open BENCHING-placement question, resolved by direct investigation

Dispatched to a research pass reading every real `mark_benching`/
`/promote` call site across `vinu-agent`, `vinu-research`, and
`vinu-live`. Confirmed:

- An artifact is created **already at `BENCHING`** (never via a separate
  `CREATED -> BENCHING` call in production) -- either from vinu-agent's
  own lighter-weight research pass (`research_artifact_writer.py`) or
  vinu-research's correlation-blocked approval path (`service.py`'s
  `approve_run()`).
- From `BENCHING`, there are **three independent, parallel** promotion
  paths, not a sequence: (a) `risk_gatekeeper` -> `PEND` ->
  `capital_allocator` -> `ACTIVE` (Phase 2, built this session); (b)
  `ShadowEvaluator`'s own paper-trading gate -> `ACTIVE` directly (real,
  now confirmed working when invoked, still not scheduled); (c)
  vinu-research's own `promote-scan` CLI / statistical bar -> `ACTIVE`
  directly.
- **Answer to `01-plan.md`'s open question**: `BENCHING` is the pre-review
  resting state, not a post-funding period -- `ShadowEvaluator` does not
  gate entry into `risk_gatekeeper`'s review, and does not interact with
  `PEND`/`PENDBLOCK` at all. It's a genuinely separate, parallel path to
  `ACTIVE` from the same `BENCHING` starting point, exactly as
  `strategy_store.py`'s own comment (written during Phase 2) already
  said: "a different, independent gate from risk_gatekeeper." No code
  change was needed to make this true -- it already was; the question was
  only ever about confirming it, which is now done.

## Test results

```
vinu-live:   122 passed (full suite; 1 new test in test_shadow_evaluator.py + 3 new in test_shadow_evaluator_real_endpoint.py)
vinu-agent:  512 passed (full suite; docs-only changes there, no test count change)
```

No regressions in either package's full suite.

## Known follow-ups (not blocking, not silently dropped)

- **Nothing calls `ShadowEvaluator.evaluate_all()` on a schedule.** This
  was true before Phase 4 and remains true after -- explicitly out of
  Phase 4's own scope (`01-plan.md` only asked to fix the endpoint,
  confirmed unnecessary, and to confirm the open BENCHING question).
  `vinu-portfolio`'s `drawdown_scheduler.py` is the real, live precedent
  for exactly this kind of "build a scheduled caller" fix, should this be
  picked up later.
- **`max_sharpe_degradation` (0.5) and `min_paper_days` (5) are
  unvalidated defaults**, same as every other not-yet-tuned threshold
  across this build (`N`, `K`, completeness tolerance, PBO bands) -- not
  pinned down by this phase, flagged consistent with that pattern.
- **This session's live-safety audit trail should be treated as a
  reminder, not just a one-time note**: a comment and a skill doc both
  independently went stale the moment the code beneath them changed and
  nobody updated the prose. Worth periodically re-verifying claims in
  `skills/live-safety/SKILL.md` against the real code the same way this
  phase just did, rather than treating it as permanently authoritative.
