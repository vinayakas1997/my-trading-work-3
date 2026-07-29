# Task 1: Hard Limit Definitions

**Status:** IN PROGRESS

## Purpose

Define the hard limit dataclasses and threshold configuration for the circuit breaker.

## Approach

- LimitConfig dataclass: max_daily_loss_pct, max_var_pct, max_greeks_exposure, max_position_count
- Thresholds as deployment-time settings (not runtime-adjustable)
- Separate module from risk-math to prevent accidental weakening

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/breaker/limits.py` | — | Created |

## Verification

- [x] Limits are configurable but not runtime-adjustable by plans/forecasts
