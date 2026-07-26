# Task 2: VaR, CVaR, and Expected Move

**Status:** PENDING

## Purpose

Implement Value-at-Risk (historical, parametric), Conditional VaR (CVaR/Expected Shortfall), and expected move formulas.

## Approach

- Historical VaR: percentile of returns over lookback window
- Parametric VaR: z-score * volatility under normal assumption
- CVaR: mean of returns beyond VaR threshold
- Expected move: standard deviation-based expected range, straddle-approximation

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_tools/compute/risk/value_at_risk.py` | — | Created |
| `vinu_tools/compute/risk/expected_move.py` | — | Created |

## Verification

- [x] Known-input/known-output tests pass against hand-computed values
