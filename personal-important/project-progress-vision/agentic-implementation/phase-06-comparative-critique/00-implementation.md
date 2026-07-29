# Phase 06: Comparative Critique Agent

**Status:** COMPLETED  
**Started:** 2026-07-24  
**Depends on:** Step 2 (catalog), Step 3 (validation)  
**Blocks:** Step 8

## What It Delivers

Cross-run reasoning in the risk critic pipeline. Before the rule-based check runs, the loop queries `research_catalog` for the symbol's lifetime history. If a symbol has been tried many times with no success, the critic short-circuits to STOP, saving LLM tokens and compute. The catalog entry is also passed to the LLM prompt for richer reasoning context.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-research/vinu_research/loop.py` | vinu-research | modify |
| `vinu-research/vinu_research/llm.py` | vinu-research | modify |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-cross-run-check.md` | Add `_cross_run_comparison()` method | DONE |
| 2 | `02-task-wire-critic.md` | Wire into `_default_risk_critic` | DONE |
| 3 | `03-task-llm-context.md` | Pass catalog_entry to LLM prompt | DONE |

## Dependencies Met

- [x] Step 2 completed — catalog table with lifetime_trial_count and best_sharpe_ever
- [x] Step 3 completed — MC validation gate
