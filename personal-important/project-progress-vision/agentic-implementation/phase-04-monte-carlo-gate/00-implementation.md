# Phase 04: Wire Monte Carlo Gate into Research Loop

**Status:** COMPLETED  
**Started:** 2026-07-24  
**Depends on:** Phase 02, Phase 03  
**Blocks:** Phase 06

## What It Delivers

- Validation data from MC algorithms is returned in the simulator API response
- `run_backtest()` defaults to `run_validation=True`
- Research loop short-circuits after the first backtest if the MC validation gate fails
- New `mc_gate_failed` hypothesis status for tracking rejected strategies

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-simulator/vinu_simulator/models/simulation.py` | vinu-simulator | modify |
| `vinu-simulator/vinu_simulator/server/schemas.py` | vinu-simulator | modify |
| `vinu-simulator/vinu_simulator/server/routes_read.py` | vinu-simulator | modify |
| `vinu-simulator/vinu_simulator/service.py` | vinu-simulator | modify |
| `vinu-research/vinu_research/models.py` | vinu-research | modify |
| `vinu-research/vinu_research/tools.py` | vinu-research | modify |
| `vinu-research/vinu_research/loop.py` | vinu-research | modify |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-expose-validation.md` | Expose validation in simulator API response | DONE |
| 2 | `02-task-run-validation-default.md` | Default `run_validation=True` in run_backtest | DONE |
| 3 | `03-task-mc-gate-status.md` | Add `mc_gate_failed` to HypothesisStatus | DONE |
| 4 | `04-task-mc-gate-loop.md` | Add gate check in StrategyResearchLoop | DONE |

## Dependencies Met

- [x] Phase 02 completed — catalog + checkpoint tables
- [x] Phase 03 completed — MC validation algorithms

## Review Findings & Fixes Applied (2026-07-24, separate review session)

An independent review found this phase's task 1 ("Expose validation in simulator API
response") only did half of what its own name implies, plus a fail-open bug in the gate itself:

- **Validation was returned but never persisted/queryable — the core problem this whole effort
  exists to fix, only half-solved.** `validation` was added to `SimulateResponse` /
  `CustomSimulateResponse`, so the **synchronous** POST `/simulate` and `/simulate/custom`
  response correctly carries it (this is what made the MC gate itself work, since
  `StrategyResearchLoop._check_mc_gate` reads the live response directly). But
  `MetaStorage.insert_run()` was never extended with a `validation` parameter, `simulation_runs`
  had no `validation` column, and `RunSummary` had no `validation`/`symbols` fields. That means
  `GET /results/{run_id}` — the **persisted, later-queryable** path — still couldn't return it,
  and `vinu-agent/vinu_agent/tools/trade_plan_tool.py._fetch_validation` (the intended consumer)
  was **never touched by this phase at all** and remained exactly as broken as before Phase 1
  started: it still filtered `/runs` results on `r.get("config", {}).get("symbols", [])`, a
  field `RunSummary` never populated, so the lookup always fell through to `"no_matching_run"`.
  - **Fix, in `vinu-simulator`**:
    - `storage/meta.py`: added `validation TEXT` and `symbols TEXT` columns to
      `simulation_runs` via a migration (`_ensure_validation_columns`, following the existing
      `_ensure_config_hash_column` pattern); `insert_run()` now accepts and persists
      `validation`/`symbols`; `get_run()`, `get_run_by_config_hash()`, and `list_runs()` all
      deserialize them back out. `list_runs()` also gained a `symbol` filter parameter
      (case-insensitive substring match against the stored `symbols` list).
    - `service.py`: reordered both `simulate()` and `_simulate_custom_impl()` so
      `insert_run()` is called **after** validation is computed (it previously ran before,
      structurally unable to include it), passing `validation=validation` and the run's actual
      symbol list.
    - `schemas.py`: added `validation`/`symbols` fields to `RunSummary`; updated the stale
      `run_validation` field docstring (it still said "not returned in API response," which
      was already false once task 1 shipped).
    - `routes_read.py`: `GET /runs` now accepts an optional `?symbol=` query param.
  - **Fix, in `vinu-agent`**: `trade_plan_tool._fetch_validation` rewritten to call
    `GET /runs?symbol=<symbol>` directly and read the real `validation`/`symbols` fields, with a
    fallback to `GET /results/{run_id}` only if the run summary's inline `validation` is absent.
    Added `tests/test_trade_plan_validation.py` (previously zero test coverage for this
    function) covering the matching-run, fallback, no-match, and error paths.
- **Fail-open gate default**: `_check_mc_gate` in `loop.py` used
  `verdict.get("passed", True)` — a validation dict present but missing/malformed `verdict`
  data would silently pass the gate. Changed to `verdict.get("passed", False)` (fail closed),
  consistent with the `compute_validation_verdict` fix in Phase 03.
- **Zero test coverage on the gate itself**: no test anywhere exercised `_check_mc_gate` or
  proved a failing verdict actually stops `StrategyResearchLoop.run()` before refinement, despite
  this being the headline feature of this phase. Added `TestCheckMcGate` to `tests/test_loop.py`
  (5 tests): no-validation-present passthrough, passing-verdict passthrough, failing-verdict
  produces a `STOP` `CriticFeedback` with reasons, missing-`verdict`-key fails closed, and an
  end-to-end test proving a failing first backtest stops `run()` after exactly one iteration
  without ever calling the risk critic.
- **Suite after fix**: 126/126 vinu-simulator + 407/407 vinu-research + 112/112 vinu-agent tests
  pass (688 total across all four touched packages including vinu-lib's unaffected 43).
