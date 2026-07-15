# Backtesting

## What This Angle Studies
Tests the full strategy backtesting pipeline: 44+ metrics across 6 categories (returns, risk ratios, drawdown, tail risk, win/loss, benchmark comparison).

## Results
_compute_metrics() produces 10 core metrics correctly. Simulator API returns 422 - strategies not registered in service. Cost models (FlatCost, AlmgrenChriss) and position sizers (Fixed, VolTarget, FractionalKelly) exist in codebase but need real strategy data.

## Execution Time
~2s

### Bugs Found
- **Bug 1**: Simulator API returns 422 on simulate — No weight data found for strategy. Strategy must be evaluated first via vinu-strategy before simulator can run. No strategy data pre-computed.. Status: Open
- **Bug 2**: No HTTP endpoint for strategy registration — Cannot POST new strategy YAML. Strategies are loaded from filesystem only; no API for dynamic registration. Status: Design