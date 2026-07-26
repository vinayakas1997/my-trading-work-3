# Phase 10: Portfolio Correlation Gate

**Status:** COMPLETED
**Started:** 2026-07-26
**Depends on:** Step 2 (catalog + strategy store)
**Blocks:** Step 11 (integration testing)

## What It Delivers

A cross-strategy correlation check that runs before a strategy is promoted to ACTIVE. When a research run is approved, the gate backtests the candidate strategy and all currently active strategies over the same date range, computes pairwise daily-return correlations, and blocks promotion if the average correlation exceeds a configurable threshold (default 0.85). Blocked strategies are created as BENCHING instead of ACTIVE, preventing redundant/highly-correlated strategies from diluting portfolio diversification.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-research/vinu_research/gates/__init__.py` | vinu-research | create |
| `vinu-research/vinu_research/gates/correlation_gate.py` | vinu-research | create |
| `vinu-research/vinu_research/promotion.py` | vinu-research | modify |
| `vinu-research/vinu_research/service.py` | vinu-research | modify |
| `vinu-research/vinu_research/config.py` | vinu-research | modify |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-correlation-gate-module.md` | CorrelationGate async check module | DONE |
| 2 | `02-task-wire-into-promotion.md` | Wire into promotion.py + service.py | DONE |
| 3 | `03-task-tests.md` | Tests for both tracks | DONE |

## Dependencies Met

- [x] Step 2 completed — research_catalog + strategy_store with Artifact/ACTIVE strategies
- [x] Step 4 completed — simulator backtest API available via ResearchTools
