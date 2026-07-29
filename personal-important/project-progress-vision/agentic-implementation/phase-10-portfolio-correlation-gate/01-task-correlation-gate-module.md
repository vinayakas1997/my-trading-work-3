# Task 1: Correlation Gate Module

**Status:** DONE

## Purpose

Create the async `CorrelationGate` module that checks whether a candidate strategy's daily returns are too correlated with existing active strategies before promotion.

## Approach

- New `gates/` package with `__init__.py` and `correlation_gate.py`
- `CorrelationVerdict` dataclass: eligible, avg_correlation, max_correlation, n_active, correlations dict, reasons
- `check_correlation_gate()` async function: backtests candidate + each active strategy over the same date range, fetches equity returns, computes pairwise Pearson correlations
- If no active strategies exist or all backtests fail: eligible=True (no strategies to correlate with)
- `_backtest_and_get_returns()` helper: runs a single backtest via `ResearchTools.run_backtest`, fetches equity returns via `fetch_equity_returns`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/gates/__init__.py` | — | Created (empty) |
| `vinu-research/vinu_research/gates/correlation_gate.py` | — | Created |

## Verification

- [x] 9 new tests pass (TestCheckCorrelationGate, TestBacktestAndGetReturns)
