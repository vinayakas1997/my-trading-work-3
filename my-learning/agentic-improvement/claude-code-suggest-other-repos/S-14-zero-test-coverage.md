# S-14: Zero Test Coverage on the Entire P1-P4 Surface

## What It Is

A search of `vinu-components/vinu-research/tests` for any of the following found
no matches: `query_by_symbol`, `memory_context`, `add_evidence`,
`reject_with_reason`, `_reflect`, `_diagnose_failure`, `_characterize_stock`,
`_validate_idea`, `_normalize_suggestion_key`. None of P1 (memory injection), P2
(self-awareness), P3 (hypothesis brain), P4 (meta-intelligence), or the R-A
through R-E fixes have any automated test coverage.

## Why It's Required

Every bug found in the first audit (hypothesis identity collision, self-
referential memory context, skipped callback on pivot, `run_id=0`, AST-failure
evidence pollution, dead suggestion-tracking) was a *logic* bug — wrong ordering,
wrong key, wrong guard condition — exactly the class of bug unit tests catch
cheaply and regression-proof permanently. R-A through R-E fixed five of them by
hand, verified by manual code reading (both in the original audit and in this
follow-up). Without tests, there's nothing stopping any of those five from
regressing silently in a future change, and nothing validating that any of the
S-01 through S-13 suggestions in this folder, if implemented, actually work as
described rather than just looking right.

## Impact

- **If unfixed:** every future change to `loop.py`/`hypothesis_registry.py`/
  `service.py` (including implementing suggestions from this folder) carries the
  same silent-regression risk that produced the original 6 bugs — verified only by
  manual reading, which is exactly how they went unnoticed the first time.
- **If fixed:** the specific bug classes already found become impossible to
  reintroduce without a failing test, and new features (S-01 through S-13) get
  built against a harness that can actually confirm they work.

## How to Use Effectively

Prioritize tests that encode the *specific* bugs already found — these are cheap
because the failure mode is already known precisely:

1. **Hypothesis matching (R-A / S-01):** two runs with different `user_idea` for
   the same symbol should create/reuse *different* hypotheses when the ideas are
   unrelated, and the *same* hypothesis when they're clearly the same strategy
   family. This is the single highest-value test — it's the bug with the highest
   blast radius (contaminates the entire "learning memory" premise) and the one
   most likely to have edge cases the substring-match fix (R-A) doesn't fully
   cover (see S-01).
2. **Memory context exclusion (R-B):** `get_past_run_summaries()` called after a
   new run is inserted with `RUNNING` status must not include that run in its
   results.
3. **Callback ordering (R-C):** when `should_pivot` is true, `on_iteration` must
   still have been called for that iteration's record before the loop breaks.
4. **`add_evidence` rejected-status guard (R-A):** adding "supports" evidence with
   high sharpe to a `rejected` hypothesis must leave its status as `rejected`, not
   flip it to `validated`.
5. **Suggestion-key normalization (R-E):** two suggestion strings differing only
   in embedded numbers (e.g. "Sharpe 1.23 is not significant" vs "Sharpe 0.89 is
   not significant") must normalize to the same tracking key.

Write these five first — each maps directly to a bug that already happened once,
so each test is cheap to write (the exact repro is already documented in
`01-later-stage-01/R-A` through `R-E`) and has already proven itself worth
catching.

## Implementation Hint — Where This Fits Today

**Entry point:** `vinu-components/vinu-research/tests/` — check
`test_routes.py`/`test_scheduled.py` (both referenced in earlier grep results)
for the existing test conventions (fixture style, whether `HypothesisRegistry`
and `StrategyResearchLoop` are already mocked anywhere) before writing new tests,
so new ones match the existing style rather than introducing a second pattern.

**Why each of the 5 tests above is cheap specifically:**
- Tests 1 and 4 (hypothesis matching, rejected-status guard) only need a
  `HypothesisRegistry` pointed at a temp directory (constructor already accepts
  `path: Path | None` — `hypothesis_registry.py:19`, built exactly for this: no
  mocking required, just `HypothesisRegistry(path=tmp_path / "test.json")`) plus
  direct calls to `create()`/`add_evidence()`/`reject_with_reason()`. No LLM, no
  network, no backtest engine involved — pure data-layer tests.
- Test 2 (memory exclusion) needs `ResearchStorage` pointed at a temp SQLite file
  (same pattern — check its constructor) plus `insert_run()` +
  `get_past_run_summaries()`. Also no LLM/network dependency.
- Test 5 (suggestion-key normalization) is a pure function test —
  `_normalize_suggestion_key` is a `@staticmethod` (`loop.py:958`), callable
  directly with no `StrategyResearchLoop` instance needed at all.
- Test 3 (callback ordering) is the only one that needs a real
  `StrategyResearchLoop.run()` invocation with mocked `quant_coder`/`risk_critic`
  callables (the constructor already accepts these as injectable params —
  `loop.py:110-118` — specifically designed for testability, no monkeypatching
  needed) and an `on_iteration` spy to assert call order against `should_pivot`.

**None of these five require live LLM calls or network access** — they're all
reachable with the existing dependency-injection points already in the
constructors (`HypothesisRegistry(path=...)`, `StrategyResearchLoop(quant_coder=...,
risk_critic=...)`), which is exactly why they're the cheapest starting point
rather than an aspirational "write full coverage" ask.

## Potential Bugs to Watch For While Testing (bugs in the tests themselves)

- **Tests accidentally touching the real `~/.vinu/hypotheses.json`.** If a test
  forgets to pass `path=tmp_path / "test.json"` to `HypothesisRegistry(...)`, it
  silently falls back to the hardcoded default (`Path.home() / ".vinu"`) and
  reads/writes the developer's or CI runner's real file. Test this by asserting
  the constructor was called with an explicit `path` in every test, or add a
  fixture that fails loudly if a test tries to touch the real default path.
- **Mock async callables that don't actually behave like coroutines.** A common
  false-positive pattern: a `quant_coder`/`risk_critic` mock returns a plain
  value instead of being properly awaitable, and depending on the mocking
  library/Python version this can either raise clearly or — worse — silently
  produce a coroutine-shaped object that the test never actually awaits,
  making the test pass without the mocked code path ever really running. Verify
  the mock is actually invoked (call count assertion) in addition to asserting
  on outcomes, so a test that "passes for the wrong reason" gets caught.
- **Parallel test execution colliding on temp paths.** If the test suite runs
  with any form of parallelism (`pytest-xdist` or similar) and two tests
  construct `HypothesisRegistry`/`ResearchStorage` against paths that aren't
  uniquely generated per test (e.g. a shared fixture-scoped temp dir reused
  across tests instead of function-scoped), expect intermittent, hard-to-
  reproduce failures — use a fresh `tmp_path` per test function, not a shared
  module/session-scoped one, for anything that does real file I/O.
- **Tests that assert on log messages instead of behavior.** Several of the
  bugs fixed by R-A..R-E manifest as `LOG.warning(...)` calls on the
  "swallowed" path (e.g. `hypothesis_registry.py:186-190`'s rejected-status
  guard). It's tempting to assert the warning was logged — prefer asserting the
  actual resulting state (`hypothesis.status == HypothesisStatus.rejected`)
  instead, since a log-message assertion breaks on harmless wording changes and
  can pass even if the underlying behavior regresses (if someone accidentally
  logs the warning but forgets to also skip the transition).
