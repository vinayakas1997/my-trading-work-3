# FP-2 🟠 Research Ignores Prior Simulation Results

**Component:** `vinu-research`, `run_pipeline.py`
**Files Changed:** `loop.py`, `run_pipeline.py`

## Problem

The pipeline runs `step_simulator` (hardcoded SMA 9/21 crossover) then `step_research` which starts from scratch — regenerates strategy code via LLM and runs its own backtests independently. Research never sees the simulator's prior strategy code, so the simulator's backtest results are wasted.

## Root Cause

Two issues:

1. **`loop.py:148` — variable shadowing bug**: The local variable `strategy_code = ""` at line 148 overwrote the incoming `strategy_code` parameter from DA-8. The parameter was silently ignored on every call, so all research runs started from scratch regardless of what was passed.

2. **`run_pipeline.py` — no code forwarding**: `step_research()` never accepted a `strategy_code` parameter and the pipeline never passed the simulator's strategy code to research. The `_CUSTOM_STRATEGY_CODE` constant (SMA 9/21 crossover) was only used by `step_simulator()`.

## Solution

**Option 2 (implemented — minimal approach): Pass strategy_code only**

- `loop.py:148`: Changed `strategy_code = ""` → `strategy_code = strategy_code or ""` to preserve the incoming parameter
- `loop.py:194`: Changed `strategy_code is None` → `not strategy_code` so either `None` or `""` triggers code generation, but a provided string skips it
- `run_pipeline.py:step_research()`: Added optional `strategy_code: str | None = None` parameter
- `run_pipeline.py:480`: Passes `_CUSTOM_STRATEGY_CODE` from the simulator step to the research step

Result: The pipeline now passes the simulator's SMA crossover code directly to research as iteration 1. Research skips code generation and runs its own backtest on the provided code, then refines it across subsequent iterations.

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `loop.py:148` | 1 | `strategy_code = ""` → `strategy_code = strategy_code or ""` |
| `loop.py:194` | 1 | `strategy_code is None` → `not strategy_code` |
| `run_pipeline.py:387-391` | ~10 | Added `strategy_code` parameter to `step_research()` |
| `run_pipeline.py:480` | 1 | Pass `_CUSTOM_STRATEGY_CODE` to research step |

## Verification

369 tests pass (1 pre-existing config env var failure).

## Future Features / Open Questions

### Option 1 (not implemented — richer but more invasive): Pass prior metrics + code

**What:** Extend the research API and loop to accept a `prior_sim_result` dict containing the simulator's full `SimulationResult` (metrics, trade log, equity curve, execution quality). The research loop could then:

1. Use the prior code as iteration 1 (same as Option 2)
2. Feed prior metrics into the LLM's refinement context so it sees execution quality data (fill rate, slippage cost, market impact)
3. Compare iteration 1's new backtest against the prior result to detect regime changes or data drift

**Where:**
- `loop.py:run()` — accept `prior_sim_result: dict | None`
- `loop.py:_default_quant_coder()` — pass prior metrics to `LlmStrategyGenerator.refine()` as additional context
- `routes_read.py:RunResearchRequest` — add `prior_sim_result` field
- `run_pipeline.py` — pass the full simulator response dict

**Why not implemented:**
- Requires schema changes to the API and careful handling of date range mismatches (simulator runs full range, research splits for holdout)
- LLM context window is a constraint — adding execution quality metrics may not improve refinement if the LLM already sees aggregate metrics
- More complex to test and maintain

**Complexity:** High
