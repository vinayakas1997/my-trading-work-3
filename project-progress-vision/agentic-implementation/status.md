# Implementation Status

Last updated: 2026-07-24

## Legend

- `not started` — No work has begun
- `in progress` — Phase folder exists, work is underway
- `completed` — All tasks done, tests pass, verified
- `blocked` — Waiting on a dependency
- `superseded` — Replaced/absorbed by another step

---

## Phase Status Overview

| Step | Phase | Status | Started | Completed | Notes |
|------|-------|--------|---------|-----------|-------|
| 1 | Harden vinu-lib primitives | `completed` | 2026-07-24 | 2026-07-24 | 4 tasks done, 43/43 tests pass, integration gap confirmed clear |
| 2 | Research/simulator catalog + checkpoints | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | ResearchStorage refactored to extend SQLiteBackend; research_catalog table; iteration_checkpoints table; simulator_catalog table. **Review found `lifetime_trial_count` was being overwritten by every run instead of reflecting the caller's true cumulative total, and the regression test encoded that as correct — fixed at the storage layer (`update_catalog_after_run` now documents/enforces overwrite-of-cumulative-total + MAX-not-overwrite for `best_sharpe_ever`) and at the caller (`prior_trials` in service.py is now fetched unconditionally, not only when `best_result` exists).** 407/407 research + 126/126 sim tests pass |
| 3 | Monte Carlo validation algorithms | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | block_bootstrap_permutation, price_path_resample, compute_validation_verdict; wired into service.py. **Review found `compute_validation_verdict` defaulted to `passed: True` when every sub-check was skipped for insufficient data — fixed to fail closed.** Also found `run_validation` was still excluded from the simulator's cache-hash (pre-existing bug from before this implementation effort, missed by phase-01/03 as originally scoped) — fixed so a validation-required call can no longer silently return a stale unvalidated cached result. 126/126 sim tests pass |
| 4 | Wire Monte Carlo gate into research loop | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | validation exposed in API response; run_validation=True default; mc_gate_failed status; gate short-circuits after first backtest. **Review found the "storage is not proper" problem this whole effort was meant to fix was only half-solved: `validation` was returned in the synchronous `/simulate` response but never persisted to `simulation_runs`/`RunSummary`, so `GET /results/{run_id}` and `GET /runs` still couldn't return it, and `vinu-agent`'s `trade_plan_tool._fetch_validation` was untouched and still broken exactly as before Phase 1 started.** Fixed: `validation`/`symbols` columns added to `simulation_runs` with a migration, `insert_run` reordered to run after validation is computed, `RunSummary`/`GET /runs` gained `validation`/`symbols` fields plus a `?symbol=` filter, and `trade_plan_tool._fetch_validation` now uses the real filtered lookup instead of a `config.symbols` field that never existed. Also fixed `_check_mc_gate`'s `verdict.get("passed", True)` fail-open default to fail closed, and added the previously-missing test coverage for the gate itself (0 tests existed for `_check_mc_gate` before this fix; 5 added, including an end-to-end test proving a failing verdict stops the loop after iteration 1 without calling the risk critic). 126/126 sim + 407/407 research + 112/112 agent tests pass |
| 5 | Migrate stock-price & news onto vinu-lib | `completed` | 2026-07-24 | 2026-07-24 | MetaBackend extends SQLiteBackend; NewsRepository extends SQLiteBackend; redundant connection mgmt removed; 33/33 stock-price + 85/85 news + 43/43 vinu-lib tests pass |
| 6 | Comparative critique agent | `completed` | 2026-07-24 | 2026-07-24 | _cross_run_comparison in _default_risk_critic; catalog_entry passed to LLM prompt; STOP on 10+ trials with Sharpe<0.3 or 5+ with Sharpe<0.1; 407/407 research + 126/126 sim + 112/112 agent tests pass |
| 7 | Unified agent-memory layer | `not started` | — | — | Cross-package view; cleanest after Step 5 |
| 8 | Trading playbook synthesis | `not started` | — | — | Extends TradePlanTool |
| 9 | Context-efficient retrieval + overfitting | `not started` | — | — | Two parallel sub-tracks after Steps 7 and 2 |
| 10 | Portfolio correlation gate | `not started` | — | — | Reads from catalog |
| 11 | Integration testing | `not started` | — | — | End-to-end; everything else must ship first |
| 12 | Shadow/live validation | `not started` | — | — | Uses `last_validated_ts` watermark from Step 2 |
| 13 | Judgment quality & cost realism | `not started` | — | — | Final phase |

---

## Superseded Phases

| Original Phase | Reason | Status |
|----------------|--------|--------|
| 01-vision-plan Phase 1 (storage half) | Replaced by Step 2 catalog design | `superseded` |
| 01-vision-plan Phase 3 (iteration storage) | Replaced by Step 2 checkpoint tables | `superseded` |

---

## Recent Activity

| Date | Step | Event |
|------|------|-------|
| 2026-07-24 | — | Initialized project-progress-vision/agentic-implementation/ with AGENTS.md, plan.md, status.md |
| 2026-07-24 | 1 | Started phase-01-harden-vinu-lib — 4 tasks planned |
| 2026-07-24 | 1 | Completed phase-01 — upsert helpers, composite-key support, sharded parquet writes, gap check. 22/22 tests pass |
| 2026-07-24 | 2 | Completed phase-02 — ResearchStorage refactored, catalog + checkpoint tables, simulator catalog. 101 + 17 = 118 tests pass |
| 2026-07-24 | 3 | Completed phase-03 — block_bootstrap, price_path_resample, compute_validation_verdict. 24 new tests, 121/121 pass |
| 2026-07-24 | 4 | Completed phase-04 — validation in API schemas/response; run_validation=True default; mc_gate_failed status; _check_mc_gate in loop short-circuits on failure. 121/121 sim + 401/401 research pass |
| 2026-07-24 | 5 | Completed phase-05 — MetaBackend extends SQLiteBackend; NewsRepository extends SQLiteBackend; redundant connection mgmt removed. 33/33 stock-price + 85/85 news + 43/43 vinu-lib tests pass |
| 2026-07-24 | 6 | Completed phase-06 — _cross_run_comparison gates on lifetime_trial_count vs best_sharpe_ever; catalog_entry passed to LLM prompt for richer context. 407/407 research + 126/126 sim + 112/112 agent = 645 tests pass |
| 2026-07-24 | 2,3,4 | Independent review of Steps 1–4 (by a separate session) found 4 confirmed bugs before sign-off: (1) `lifetime_trial_count` overwritten per-run instead of reflecting the true cumulative total, with the regression test encoding the bug as correct; (2) `compute_validation_verdict` and `_check_mc_gate` both fail-open (default to "passed") when validation data is missing, undermining the "hard, un-bypassable gate" design intent; (3) `validation`/`symbols` were never persisted to the queryable `simulation_runs` table or `RunSummary` — the exact "orphaned run_card.json" problem Phase 1 was created to fix was only half-solved; (4) the simulator's cache-hash still excluded `run_validation`, a pre-existing bug missed by this effort's own scope. All four fixed in this same session, with new regression tests for each (`_check_mc_gate` had zero test coverage before this — 5 tests added). Full suite after fixes: 43 vinu-lib + 126 vinu-simulator + 407 vinu-research + 112 vinu-agent = 688 tests, all passing. |
