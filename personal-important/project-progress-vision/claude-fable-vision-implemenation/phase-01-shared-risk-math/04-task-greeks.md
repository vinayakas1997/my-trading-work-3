# Task 4: Black-Scholes Greeks

**Status:** PENDING

## Purpose

Implement Black-Scholes analytical greeks (delta, gamma, vega, theta, rho).

## Approach

- Standard Black-Scholes closed-form formulas
- Callers provide spot, strike, time-to-expiry, IV, risk-free rate
- No options data pipeline — pure computation library

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_tools/compute/risk/greeks.py` | — | Created |

## Verification

- [x] Greeks match reference Black-Scholes values for fixed inputs
