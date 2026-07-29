# DA-8 🟠 Research Has No `strategy_code` Parameter

**Component:** `vinu-research`
**Files Changed:** `routes_read.py`, `service.py`, `loop.py`, `cli.py`

## Problem

The `RunResearchRequest` schema had no `strategy_code` field, so external callers (vinu-agent, run_pipeline.py) could never submit pre-written strategy code for evaluation through the research validation pipeline. The only way to drive research was via `user_idea` (natural language).

## Root Cause

Missing optional `strategy_code` parameter at all 4 layers: API schema, service, loop, and CLI.

## Solution

Added `strategy_code: str | None = None` at every layer. When provided:
- **Iteration 1**: Skips `_quant_coder()` generation and uses the provided code directly
- **Iteration 2+**: `user_idea` flows through the existing refinement context as guidance for the LLM refiner
- The full validation pipeline (holdout gate, walk-forward, stress test, deflated Sharpe) runs as normal

## Files Changed

| File | Change |
|------|--------|
| `routes_read.py:18-22` | Added `strategy_code` to `RunResearchRequest` and passed it through |
| `service.py:64,114` | Added `strategy_code` param to `run_research()`, passed to `loop.run()` |
| `loop.py:133,193` | Added `strategy_code` param to `run()`, skip `_quant_coder` when provided |
| `cli.py:117-121,231-238,282` | Added `--strategy-code` argument, reads file, passes to `loop.run()` |

## Verification

All 368 existing tests pass (2 pre-existing failures: config env var, SQLite concurrency).

## Future Validation Gaps (noted for later)

- Monte Carlo simulation (bootstrap/randomized backtesting for confidence intervals)
- ML-based strategy validation
- Parameter sensitivity analysis (grid search)
- Walk-forward results should gate PASS (not just informational)
- Regime-aware validation beyond fixed crisis windows
