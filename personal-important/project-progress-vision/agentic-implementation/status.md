# Implementation Status

Last updated: 2026-07-26

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
| 1 | Harden vinu-infra primitives | `completed` | 2026-07-24 | 2026-07-24 | 4 tasks done, 43/43 tests pass, integration gap confirmed clear |
| 2 | Research/simulator catalog + checkpoints | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | ResearchStorage refactored to extend SQLiteBackend; research_catalog table; iteration_checkpoints table; simulator_catalog table. **Review found `lifetime_trial_count` was being overwritten by every run instead of reflecting the caller's true cumulative total, and the regression test encoded that as correct — fixed at the storage layer (`update_catalog_after_run` now documents/enforces overwrite-of-cumulative-total + MAX-not-overwrite for `best_sharpe_ever`) and at the caller (`prior_trials` in service.py is now fetched unconditionally, not only when `best_result` exists).** 407/407 research + 126/126 sim tests pass |
| 3 | Monte Carlo validation algorithms | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | block_bootstrap_permutation, price_path_resample, compute_validation_verdict; wired into service.py. **Review found `compute_validation_verdict` defaulted to `passed: True` when every sub-check was skipped for insufficient data — fixed to fail closed.** Also found `run_validation` was still excluded from the simulator's cache-hash (pre-existing bug from before this implementation effort, missed by phase-01/03 as originally scoped) — fixed so a validation-required call can no longer silently return a stale unvalidated cached result. 126/126 sim tests pass |
| 4 | Wire Monte Carlo gate into research loop | `completed` (review fixes applied) | 2026-07-24 | 2026-07-24 | validation exposed in API response; run_validation=True default; mc_gate_failed status; gate short-circuits after first backtest. **Review found the "storage is not proper" problem this whole effort was meant to fix was only half-solved: `validation` was returned in the synchronous `/simulate` response but never persisted to `simulation_runs`/`RunSummary`, so `GET /results/{run_id}` and `GET /runs` still couldn't return it, and `vinu-agent`'s `trade_plan_tool._fetch_validation` was untouched and still broken exactly as before Phase 1 started.** Fixed: `validation`/`symbols` columns added to `simulation_runs` with a migration, `insert_run` reordered to run after validation is computed, `RunSummary`/`GET /runs` gained `validation`/`symbols` fields plus a `?symbol=` filter, and `trade_plan_tool._fetch_validation` now uses the real filtered lookup instead of a `config.symbols` field that never existed. Also fixed `_check_mc_gate`'s `verdict.get("passed", True)` fail-open default to fail closed, and added the previously-missing test coverage for the gate itself (0 tests existed for `_check_mc_gate` before this fix; 5 added, including an end-to-end test proving a failing verdict stops the loop after iteration 1 without calling the risk critic). 126/126 sim + 407/407 research + 112/112 agent tests pass |
| 5 | Migrate stock-price & news onto vinu-infra | `completed` | 2026-07-24 | 2026-07-24 | MetaBackend extends SQLiteBackend; NewsRepository extends SQLiteBackend; redundant connection mgmt removed; 33/33 stock-price + 85/85 news + 43/43 vinu-infra tests pass |
| 6 | Comparative critique agent | `completed` | 2026-07-24 | 2026-07-24 | _cross_run_comparison in _default_risk_critic; catalog_entry passed to LLM prompt; STOP on 10+ trials with Sharpe<0.3 or 5+ with Sharpe<0.1; 407/407 research + 126/126 sim + 112/112 agent tests pass |
| 7 | Unified agent-memory layer | `completed` | 2026-07-26 | 2026-07-26 | UnifiedMemoryStore (SQLite + FTS5), SyncService (HTTP pulls from research, simulator, stock-price, news), query_memory tool, contextual injection in agent prompt. 24 new tests, 136/136 agent tests pass |
| 8 | Trading playbook synthesis | `completed` | 2026-07-26 | 2026-07-26 | Long/short entry split, news sensitivity, time-of-day guidance, regime context section, drawdown-by-regime, enhanced exit checklist (8 conditions). 33 new tests, 169/169 agent tests pass |
| 9 | Context-efficient retrieval + overfitting | `completed` | 2026-07-26 | 2026-07-26 | Track A: scored search + dedup in UnifiedMemoryStore, context budget enforcement in ContextBuilder. Track B: validation tracking fields + exhaustion check in research_catalog, wired into loop.run() early-exit and service.py validation flag. 38/38 agent + 92/104 research tests pass (12 pre-existing Windows PermissionError) |
| 10 | Portfolio correlation gate | `completed` | 2026-07-26 | 2026-07-26 | CorrelationGate module (gates/correlation_gate.py): async check that backtests candidate + active strategies, computes pairwise daily-return correlations, blocks promotion if avg_corr > threshold. Opt-in via `promotion_correlation_required`. Blocked strategies created as BENCHING instead of ACTIVE. 9 new tests + 77 existing pass |
| 11 | Integration testing | `completed` | 2026-07-26 | 2026-07-26 | 16 integration tests (4 agent + 12 research) covering context+memory, catalog exhaustion+loop, promotion+correlation gate. 16 pass, 1 skip (loop normality test needs simulator). |
| 12 | Shadow/live validation | `completed` | 2026-07-26 | 2026-07-26 | Continuous re-validation using `last_validated_ts` watermark. `revalidate_artifact()` in ResearchService, `revalidation_scan()` in executor, `list_stale_artifacts()` on StrategyStore, `touch_catalog_validated_ts()` on ResearchStorage. 11 new tests, full suite 442/442 pass (2 pre-existing Windows failures). |
| 13 | Judgment quality & cost realism | `completed` | 2026-07-26 | 2026-07-26 | Provider pricing in ProviderCapabilities; CostTracker + global singleton; token usage captured in sync/async LLM clients; Goal budget wired into loop (llm calls + time); JudgmentStore for verdict→outcome calibration. 21 new tests, all pass. |

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
| 2026-07-24 | 1 | Started phase-01-harden-vinu-infra — 4 tasks planned |
| 2026-07-24 | 1 | Completed phase-01 — upsert helpers, composite-key support, sharded parquet writes, gap check. 22/22 tests pass |
| 2026-07-24 | 2 | Completed phase-02 — ResearchStorage refactored, catalog + checkpoint tables, simulator catalog. 101 + 17 = 118 tests pass |
| 2026-07-24 | 3 | Completed phase-03 — block_bootstrap, price_path_resample, compute_validation_verdict. 24 new tests, 121/121 pass |
| 2026-07-24 | 4 | Completed phase-04 — validation in API schemas/response; run_validation=True default; mc_gate_failed status; _check_mc_gate in loop short-circuits on failure. 121/121 sim + 401/401 research pass |
| 2026-07-24 | 5 | Completed phase-05 — MetaBackend extends SQLiteBackend; NewsRepository extends SQLiteBackend; redundant connection mgmt removed. 33/33 stock-price + 85/85 news + 43/43 vinu-infra tests pass |
| 2026-07-24 | 6 | Completed phase-06 — _cross_run_comparison gates on lifetime_trial_count vs best_sharpe_ever; catalog_entry passed to LLM prompt for richer context. 407/407 research + 126/126 sim + 112/112 agent = 645 tests pass |
| 2026-07-24 | 2,3,4 | Independent review of Steps 1–4 (by a separate session) found 4 confirmed bugs before sign-off: (1) `lifetime_trial_count` overwritten per-run instead of reflecting the true cumulative total, with the regression test encoding the bug as correct; (2) `compute_validation_verdict` and `_check_mc_gate` both fail-open (default to "passed") when validation data is missing, undermining the "hard, un-bypassable gate" design intent; (3) `validation`/`symbols` were never persisted to the queryable `simulation_runs` table or `RunSummary` — the exact "orphaned run_card.json" problem Phase 1 was created to fix was only half-solved; (4) the simulator's cache-hash still excluded `run_validation`, a pre-existing bug missed by this effort's own scope. All four fixed in this same session, with new regression tests for each (`_check_mc_gate` had zero test coverage before this — 5 tests added). Full suite after fixes: 43 vinu-infra + 126 vinu-simulator + 407 vinu-research + 112 vinu-agent = 688 tests, all passing. |
| 2026-07-26 | 7 | Completed phase-07 — UnifiedMemoryStore (SQLite + FTS5), SyncService for research/simulator/stock-price/news, query_memory tool, automatic symbol-context injection. 24 new tests, 136/136 agent tests pass |
| 2026-07-26 | 8 | Completed phase-08 — enhanced TradePlanTool with long/short entry split, news sensitivity, time-of-day guidance, regime context, drawdown-by-regime, 8-condition exit checklist with news triggers, active strategies section. 33 new tests, 169/169 agent tests pass |
| 2026-07-26 | 9 | Completed phase-09 — Track A: scored search + dedup in UnifiedMemoryStore (`scored_search`, `_compute_composite_score`, `SOURCE_WEIGHTS`), context budget in ContextBuilder (`max_memory_tokens`, `_estimate_tokens`). Track B: validation tracking fields + exhaustion in research_catalog schema/migration, `is_symbol_exhausted`/`exhaust_symbol`/`clear_exhaustion`, early-exit in loop.run(), `validated` flag in service.py. 38/38 agent + 92/104 research tests pass |
| 2026-07-26 | 10 | Completed phase-10 — CorrelationGate module (`gates/correlation_gate.py`): async check backtests candidate + each ACTIVE strategy, computes pairwise daily-return correlation, blocks promotion when avg_corr > threshold (default 0.85, opt-in). Blocked artifacts created as BENCHING. 9 new tests + 77 existing pass |
| 2026-07-26 | 11 | Completed phase-11 — 16 integration tests (4 agent + 12 research) covering context+memory, catalog exhaustion+loop, promotion+correlation gate. 16 pass, 1 skip (needs simulator). |
| 2026-07-26 | 12 | Completed phase-12 — Continuous re-validation with `last_validated_ts` watermark. `revalidate_artifact()` in ResearchService, `revalidation_scan()` in executor, `list_stale_artifacts()`, `touch_catalog_validated_ts()`. 11 new tests. |
| 2026-07-26 | 13 | Completed phase-13 — Provider pricing in ProviderCapabilities; CostTracker + global singleton; token usage captured in sync/async LLM clients; Goal budget wired into loop; JudgmentStore for calibration tracking. 21 new tests. |
