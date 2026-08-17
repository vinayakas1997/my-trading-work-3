---
name: phase-2-implement-test
status: built -- Phase 2 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 2 -- Implementation record

Built 2026-08-11, directly following Phase 1 in the same session.

## Real gaps found beyond the original plan

1. **vinu-portfolio's real routes are all parameterless GETs reading its
   own persisted book** (`/portfolio/state`, `/weights`, `/daily-
   allocation`, ...) -- there was no way to ask "what would this PEND
   batch's weights look like" without those artifacts already being
   ACTIVE, which is circular (Phase 2's whole point is deciding ACTIVE
   status). Fixed with a new `POST /portfolio/evaluate-batch` plus a
   `build_portfolio(extra_candidates=...)` / `compute_daily_allocation
   (extra_candidates=...)` parameter on `PortfolioService` -- additive,
   backward-compatible, real risk-parity/correlation math reused as-is.
2. **`risk_gatekeeper` never produced a dollar size, only APPROVED/
   REJECTED** -- the guard rail's `min(risk_gatekeeper's approved size,
   vinu-portfolio's computed size)` cap had nothing on the left side to
   read. Fixed by having `exposure_reviewer` compute and report the real
   concentration-limit headroom (`APPROVED_SIZE:` in its output), threaded
   through the manager's JSON block, and persisted via a new
   `Artifact.approved_size` column set by `mark_pend()`.
3. **`allocate_risk_parity`'s result carried no `artifact_id`** -- a
   caller evaluating a mixed batch (real ACTIVE book + PEND candidates)
   had no reliable way to map a returned weight back to a specific
   candidate (name-string matching only). Added `artifact_id`/
   `is_candidate` to each weight entry, carried through from the input.

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/vinu-portfolio/vinu_portfolio/service.py` | modified | `allocate_risk_parity` result entries gain `artifact_id`/`is_candidate`. `build_portfolio`/`compute_daily_allocation` gain an optional `extra_candidates` param (additive, no-arg behavior unchanged). |
| `vinu-components/vinu-portfolio/vinu_portfolio/server/app.py` | modified | New `POST /portfolio/evaluate-batch` (`EvaluateBatchRequest`/`BatchCandidate` models), shapes candidates into `list_active_strategies()`'s own dict shape and calls `build_portfolio`/`compute_daily_allocation` with them. |
| `vinu-components/vinu-portfolio/tests/test_service.py` | modified | 4 new tests: extra-candidate weighting, no-arg behavior preserved, PEND-vs-PEND correlation reflected in the matrix. |
| `vinu-components/vinu-portfolio/tests/test_app_evaluate_batch.py` | new | 3 route tests -- first route-level tests in this package (app.py has no DI hook; patched `PortfolioService` at the class level, works since Python resolves methods at call time). |
| `vinu-components/vinu-research/vinu_research/models.py` | modified | `ArtifactStatus.PEND` added. `Artifact.approved_size: float = 0.0` added. |
| `vinu-components/vinu-research/vinu_research/storage/strategy_store.py` | modified | Schema + migration for `approved_size`. `_ALLOWED_TRANSITIONS`: `PEND` added as a new option alongside (not replacing) `BENCHING`/`MONITORING` -> `ACTIVE` -- see deviation note below. New `mark_pend(artifact_id, approved_size=...)`. |
| `vinu-components/vinu-research/tests/test_strategy_store_transitions.py` | modified | 8 new tests (PEND transitions, approved_size persistence, idempotency, invalid-transition cases) + 1 regression test confirming the direct BENCHING->ACTIVE path (ShadowEvaluator's, untouched) still works. |
| `vinu-components/vinu-agent/vinu_agent/agent/risk_gatekeeper_hook.py` | modified | Calls `mark_pend(artifact_id, approved_size=...)` instead of `mark_active`. Writes a best-effort `TickerLedger` row (never blocks the real transition). |
| `vinu-components/vinu-agent/vinu_agent/agent/capital_allocator_hook.py` | new | Mirrors risk_gatekeeper_hook.py's shape: parses the manager's final JSON, calls `mark_active()` for every `funded: true` candidate, writes a `TickerLedger` row per funded transition. |
| `vinu-components/vinu-agent/vinu_agent/agent/team.py` | modified | `TeamManager`/`_apply_team_result_hook` thread `ticker_ledger_store` through; new `capital_allocator` dispatch case. |
| `vinu-components/vinu-agent/vinu_agent/tools/delegate_tool.py`, `vinu_agent/tools/__init__.py`, `vinu_agent/session/service.py`, `vinu_agent/service.py` | modified | `ticker_ledger_store` threaded end-to-end from `AgentService` (built in Phase 0, unused until now) through `SessionService` -> `build_registry` -> `DelegateToTeamTool` -> `TeamManager`. |
| `vinu-components/vinu-agent/vinu_agent/tools/allocation_tool.py` | rewritten | `ComputeAllocationCandidatesTool` now: filters to `PEND` (not `ACTIVE`), calls `POST /portfolio/evaluate-batch` for real weights (one call for the whole batch), caps each at `min(approved_size, portfolio_computed_size)`, fails closed (never falls back to the old fixed-fraction math) on an unreachable vinu-portfolio, and writes best-effort `TickerLedger` skip rows. |
| `vinu-components/vinu-agent/tests/test_allocation_tool.py` | rewritten | 10 tests covering the new PEND/vinu-portfolio-backed behavior, the never-exceeds-approved-size cap, the unreachable-fails-closed case, and one-call-per-batch. |
| `vinu-components/vinu-agent/tests/test_team.py` | modified | `TestRiskGatekeeperHook` updated for the real PEND (not ACTIVE) outcome + a new TickerLedger test. New `TestCapitalAllocatorHook` (4 tests): funded->ACTIVE, TickerLedger row, nothing-funded leaves PEND, invalid-transition swallowed. |
| `vinu-components/vinu-agent/teams/risk_gatekeeper/agents/exposure_reviewer/prompt.md`, `manager_prompt.md` | modified | `exposure_reviewer` now computes and reports `APPROVED_SIZE`; the JSON block carries `approved_size`. |
| `vinu-components/vinu-agent/teams/capital_allocator/TEAM.md`, `manager_prompt.md`, `agents/allocation_analyst/AGENT.md`, `prompt.md` | modified | Reframed around the PEND batch + vinu-portfolio sizing instead of the old ACTIVE-list + fixed-fraction/deflated_sharpe method. Explicit "don't invent a fallback funding decision on error" instruction. |

## Design deviations from `01-plan.md`/`02-guard-rail.md`, and why

- **`BENCHING`/`MONITORING` -> `ACTIVE` transitions were kept, not
  replaced by `PEND`.** Direct code reading found `vinu-live`'s
  `ShadowEvaluator` promotes `BENCHING` -> `ACTIVE` via its own HTTP call
  to vinu-research, entirely independent of `risk_gatekeeper_hook.py`.
  Phase 4's own plan flags "where BENCHING sits relative to Phase 2/3's
  states" as an open question needing vinu-live's real callers read
  first -- done here, but the reconciliation itself is left to Phase 4,
  not decided by force here. `risk_gatekeeper_hook.py` itself was still
  changed to only ever request `PEND`, never `ACTIVE` directly -- the
  *hook's* behavior fully matches the plan; the *transition table*
  stayed permissive rather than becoming a second, conflicting source of
  truth about ShadowEvaluator's own promotion path.
- **The "cadence batch boundary" edge case is resolved by construction,
  not by a timestamp rule.** `02-guard-rail.md` worried about an artifact
  transitioning to `PEND` at the exact moment a cadence run starts,
  needing an explicit `>`/`>=` rule to land in exactly one run. The real
  implementation never windows by timestamp at all --
  `ComputeAllocationCandidatesTool`/capital_allocator's manager task is
  handed a fresh `list_artifacts(status=PEND)`-derived id list each time
  it runs, and `get_artifact()` re-fetches each one immediately before
  sizing it (the staleness re-check `01-plan.md` item 4 already called
  for). A funded artifact leaves `PEND` immediately (`mark_active`), so
  it cannot appear in a later run's list; an artifact that arrives after
  one run started simply isn't in that run's list and is picked up by the
  next one. This sidesteps the exact race the guard rail worried about
  rather than needing a carefully-tested boundary rule.
- **No standalone scheduler/cadence-loop module was built.** Consistent
  with Phase 0/1's already-established, real gap: no cron/scheduler
  mechanism exists anywhere in this codebase yet. `capital_allocator`'s
  batching is real and testable (the manager gets every PEND id in one
  task, not one at a time) but something still needs to construct that id
  list and invoke `delegate_to_team("capital_allocator", ...)` on an
  actual interval -- exactly the same "not wired to a live loop" state
  Phase 0's `RunLogTrigger`/`ChangeGate` are already in.

## Test results

```
vinu-portfolio:  113 passed (full suite; 4 new service tests + 3 new route tests)
vinu-research:   580 passed, 1 skipped (full suite; 8 new PEND-transition tests, unrelated pre-existing skip)
vinu-agent:      498 passed (full suite; 10 rewritten allocation_tool tests + 8 rewritten/new team.py hook tests)
```

No regressions in any of the three packages' full suites.

## Known follow-ups (not blocking, not silently dropped)

- **`budget` (capital_allocator's total risk figure) has no automated
  source yet** -- it's a caller-supplied number, same as the pre-Phase-2
  tool. A natural future source is the same account-equity fetch
  vinu-portfolio's own `compute_daily_allocation` already performs
  (`_fetch_account_equity`), but wiring that in is a separate, undecided
  step, not assumed here.
- **PEND age/staleness has no auto-expiry**, per the guard rail's own
  explicit non-requirement -- every PEND transition and skip is now
  `TickerLedger`-visible (satisfying "a human can see it"), but nothing
  alerts on a PEND item that's been stuck for N cycles. Natural candidate
  for Phase 7 (Significance Triage) once that phase's pattern-detection
  exists.
- **`risk_gatekeeper`'s `APPROVED_SIZE` computation is prompt-driven
  arithmetic, not independently double-checked.** `exposure_reviewer`
  computes it from the same `get_portfolio()` data it already reads; no
  second, deterministic tool verifies the LLM's arithmetic before it
  becomes the real funding cap. Worth a follow-up if a wrong number here
  is ever observed in practice -- not treated as a blocking risk now
  since it can still only ever be sized DOWN, never up, by
  `capital_allocator`'s later cap.
