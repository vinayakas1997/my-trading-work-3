# DA-36 🟡 Simulator Always Computes All 30+ Metrics

**Component:** `vinu-simulator`
**Files Changed:** `simulation.py`, `metrics.py`, `simulator.py`, `schemas.py`, `service.py`

## Problem

`compute_full_metrics()` always computed both basic (10) and extended (~25) metrics. Extended metrics — VaR, CVaR, tail ratio, drawdown duration, win/loss ratios, benchmark beta/alpha, Sharpe CI, turnover — are expensive to compute but rarely displayed by the UI.

## Root Cause

`compute_full_metrics()` unconditionally called `compute_extended_metrics()` after `compute_performance_metrics()` with no switch to skip it.

## Solution

1. Added `full_metrics: bool = True` to `SimulationConfig`
2. Added `full: bool = True` param to `compute_full_metrics()` — when `False`, skips the extended computation entirely
3. Passed `full=config.full_metrics` from `WeightSimulator.run()` to `compute_full_metrics()`
4. Added `full_metrics` field to both `SimulateRequest` and `CustomSimulateRequest` schemas
5. Passed `full_metrics` from request to `SimulationConfig` in both `simulate()` and `simulate_custom()` service methods

**Basic metrics** (always computed):
`total_return`, `cagr`, `annual_volatility`, `sharpe_ratio`, `sortino_ratio`, `max_drawdown`, `calmar_ratio`, `win_rate`, `skewness`, `kurtosis`

**Extended metrics** (skipped when `full=False`):
`var_95`, `var_99`, `cvar_95`, `tail_ratio`, `max_dd_duration_days`, `avg_drawdown`, `recovery_time_days`, `profit_factor`, `avg_win_pct`, `avg_loss_pct`, `win_loss_ratio`, `hit_rate`, `beta`, `alpha`, `tracking_error`, `information_ratio`, `market_correlation`, `up_capture`, `down_capture`, `sharpe_standard_error`, `sharpe_p_value`, `sharpe_ci_95_low`, `sharpe_ci_95_high`, `annual_turnover`

## Files Changed

| File | Lines | Change |
|------|-------|--------|
| `models/simulation.py:50-52` | Added | `full_metrics: bool = True` to `SimulationConfig` |
| `engine/metrics.py:225,228-232` | Changed | Added `full: bool = True` param; early return when `not full` with sanitized basic metrics only |
| `engine/simulator.py:281` | Changed | Pass `full=config.full_metrics` to `compute_full_metrics()` |
| `server/schemas.py:24,84` | Added | `full_metrics` field in both request schemas |
| `service.py:84,209` | Changed | Pass `full_metrics` from request to `SimulationConfig` |

## Verification

92 simulator tests pass (0 failures). Default `full=True` preserves existing behavior for all callers.
