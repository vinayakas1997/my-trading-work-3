# Task 3: Position-Sizing Math

**Status:** PENDING

## Purpose

Implement position-sizing formulas: Kelly-optimal fraction, risk-budget-constrained size, and volatility-parity allocation.

## Approach

- Kelly criterion: optimal fraction = (p * win_avg - (1-p) * loss_avg) / (win_avg * loss_avg)
- Risk-budget sizing: size = risk_budget / (volatility * z_score)
- Volatility parity: inverse-vol weights across a basket

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_tools/compute/risk/position_sizing.py` | — | Created |

## Verification

- [x] Position size never exceeds stated risk budget across randomized combinations
