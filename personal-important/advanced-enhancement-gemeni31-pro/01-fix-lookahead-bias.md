# Phase 1: Eradicate Lookahead Bias and Ensure Data Integrity

## The Problem
The current system has a critical flaw: Lookahead bias. This is the cardinal sin of quant finance. If the simulator uses future data to make decisions today, the backtest results are entirely invalid and will fail in live trading.

The primary culprits identified in the audit are:
1. **The `bfill()` Leak**: When aligning price data or indicators, using `bfill()` (backward fill) takes a price from tomorrow and fills a missing value for today. This allows the strategy to "know" future prices.
2. **Same-Bar Signal/Execution**: If a signal is generated based on the `close` price of day `T`, you cannot execute the trade at the `open` or `close` price of day `T`. You must execute at day `T+1`.

## How to Fix It

### 1. Remove `bfill()` in `custom_sim.py` and `simulator.py`
**Target Files:** `vinu-simulator/vinu_simulator/engine/custom_sim.py`, `vinu-simulator/vinu_simulator/engine/simulator.py`

**Implementation Steps:**
- Search for any instance of `.bfill()` or `.fillna(method='bfill')` on price data or indicator DataFrames.
- Replace it with `.ffill()` (forward fill) ONLY, or drop the NaN values.
- **Edge Case:** If removing `bfill()` results in leading NaNs (because the strategy starts before data is available), handle this by delaying the start of the backtest calendar to match the first valid price data point, rather than hallucinating prices backward.

### 2. Enforce T+1 Execution Delay
**Target Files:** `vinu-simulator/vinu_simulator/engine/simulator.py`

**Implementation Steps:**
- Audit the execution loop. When the strategy yields a signal on `date[i]`, the engine must record the trade to execute on `date[i+1]` (next open) or `date[i]` but only if the signal was generated from `date[i-1]` data.
- Modify the engine's state machine so that `signals` are shifted by 1 index relative to `prices`.
```python
# Example Fix: Shift signals by 1 to ensure they only act on next day's prices
signals = signals.shift(1).fillna(0)
```

## Definition of Done
- A synthetic test where a strategy perfectly predicts tomorrow's close price should yield zero or negative return because it executes a day late.
- No `bfill()` calls exist anywhere in the data preprocessing pipeline.
