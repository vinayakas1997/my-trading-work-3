# Phase 3: Cost Models, Benchmarks, and Filter Validation

## The Problem
A strategy's theoretical edge is often destroyed by real-world friction. The audit revealed that while an `AlmgrenChrissCostModel` was written, the engine hardcodes a `FlatCostModel`. Furthermore, missing volume data silently zeroes out market impact, and CAGR calculations are inconsistent. Finally, filter generation is prone to injecting irrelevant code due to naive substring matching.

## How to Fix It

### 1. Wire Realistic Transaction Costs
**Target Files:** `vinu-simulator/vinu_simulator/engine/simulator.py`, `vinu-simulator/vinu_simulator/engine/cost_models.py`

**Implementation Steps:**
- **Dynamic Selection:** Modify the simulator configuration to accept a `cost_model` parameter, defaulting to `AlmgrenChrissCostModel` instead of `FlatCostModel`.
- **Zero Volume Bug:** In the cost model logic, if `volume` is 0 or NaN, it should raise a warning and apply a maximum penalty (or assume an extremely illiquid spread), rather than calculating 0 impact.
- **Financing Costs:** Add a `risk_free_rate` and `short_borrow_fee` to the engine. Deduct these from the daily returns before calculating the Sharpe ratio.

### 2. Fix Benchmark CAGR and Ranking
**Target Files:** `vinu-simulator/vinu_simulator/metrics/benchmark.py`, `vinu-research/vinu_research/loop.py`

**Implementation Steps:**
- Standardize the CAGR calculation. Use the geometric mean formula: `(Final Value / Initial Value) ^ (1 / Years) - 1`. Ensure all reporting functions call this single source of truth.
- Wire `rank_candidates`: In `loop.py`, instead of blindly picking `candidates[0]`, evaluate all candidates using the existing `rank_candidates` function and select the highest-scoring one.

### 3. Data-Aware Filter Generation
**Target Files:** `vinu-research/vinu_research/filters.py`

**Implementation Steps:**
- Deprecate substring matching (`"cool" in text`).
- Require the LLM to output structured JSON representing the desired filter (e.g., `{"filter_type": "volatility_guard", "indicator": "ATR", "threshold": 1.5}`).
- The system then maps this JSON to verified, safe code templates, ensuring it only references columns that actually exist in the current dataset.

## Definition of Done
- A backtest on a highly illiquid penny stock shows a massively higher cost penalty than one on a mega-cap stock like AAPL.
- CAGR matches exactly across all benchmark and strategy reports.
- Injecting random text into the LLM critique no longer results in arbitrary code filters being applied.
