# Task 1: Realized and Conditional Volatility

**Status:** IN PROGRESS

## Purpose

Implement realized volatility (simple, exponential-weighted) and conditional volatility via GARCH(1,1)/EGARCH models as pure numpy computations in `vinu_tools/compute/risk/`.

## Approach

- Realized vol: rolling window std with configurable annualization factor
- EWMA vol: exponentially-weighted with configurable decay factor lambda
- GARCH(1,1): maximum likelihood estimation via scipy optimization (fallback to method-of-moments if scipy unavailable)
- EGARCH: asymmetric conditional vol capturing leverage effect

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_tools/compute/risk/volatility.py` | — | Created |

## Verification

- [x] Known-input/known-output tests pass
- [x] Conditional vol tracks clustering pattern on known vol-spike historical series
- [x] No runtime LLM call introduced
