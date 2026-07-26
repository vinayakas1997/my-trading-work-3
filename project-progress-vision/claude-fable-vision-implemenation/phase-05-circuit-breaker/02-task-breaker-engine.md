# Task 2: Circuit Breaker Engine

**Status:** PENDING

## Purpose

Implement the circuit breaker engine that checks all limits before every order using Phase 1's dynamic covariance across Phase 3's live book.

## Approach

- check_limits(): evaluates all hard limits against current book state
- cluster-aware VaR: uses Phase 1 dynamic covariance across all positions (not independent per-symbol)
- Returns BreakerVerdict (ALLOW / HALT) with reason
- Must be the last check before any order submission

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/breaker/engine.py` | — | Created |
| `vinu_live/breaker/__init__.py` | — | Created |

## Verification

- [x] Synthetic book within limits → ALLOW
- [x] Synthetic book exceeding any limit → HALT
- [x] Cluster-aware: positions in same shock cluster flagged even if individually within limits
- [x] No code path can place an order without this check
