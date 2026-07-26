# Phase 1: Shared Risk-Math Library

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Source doc:** ../claude-fable-vision/phase-01-shared-risk-math.md
**Depends on:** —
**Blocks:** Phase 2, Phase 4, Phase 5

## What It Delivers

A new computation category inside `vinu-tools` (`compute/risk`) providing:
- Realized volatility (various window/decay schemes)
- Conditional volatility via GARCH(1,1)/EGARCH
- Value-at-Risk (historical, parametric, CVaR)
- Expected move formulas
- Position-sizing math (Kelly-optimal, risk-budget-constrained)
- Black-Scholes greeks (delta, gamma, vega, theta)
- Dynamic shrinkage-estimated covariance (Ledoit-Wolf) across arbitrary symbol sets

Pure deterministic arithmetic — no LLM, no storage dependency beyond reading price data.

## Open Questions Resolved

- **Greeks data source:** No options data/pricing path exists in the codebase. Greeks will use the Black-Scholes analytical formula with configurable IV/spot/vol inputs — callers provide the IV surface. This is consistent with the source doc's note that greeks scope depends on data availability.
- **Covariance scope:** Phase 5's circuit breaker needs dynamic covariance across the live book's symbol set, not the whole universe. Implementation provides a function that takes an arbitrary symbol list.

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu_tools/compute/risk/__init__.py` | vinu-tools | create |
| `vinu_tools/compute/risk/volatility.py` | vinu-tools | create |
| `vinu_tools/compute/risk/value_at_risk.py` | vinu-tools | create |
| `vinu_tools/compute/risk/expected_move.py` | vinu-tools | create |
| `vinu_tools/compute/risk/position_sizing.py` | vinu-tools | create |
| `vinu_tools/compute/risk/greeks.py` | vinu-tools | create |
| `vinu_tools/compute/risk/covariance.py` | vinu-tools | create |

## Tasks in this Phase

| # | Task File | Description | Status |
|---|-----------|-------------|--------|
| 1 | `01-task-realized-volatility.md` | Realized vol, GARCH/EGARCH conditional vol | DONE |
| 2 | `02-task-var-and-expected-move.md` | VaR, CVaR, expected move | DONE |
| 3 | `03-task-position-sizing.md` | Position-sizing math | DONE |
| 4 | `04-task-greeks.md` | Black-Scholes greeks | DONE |
| 5 | `05-task-dynamic-covariance.md` | Ledoit-Wolf dynamic covariance | DONE |

## Dependencies Met

- [x] No dependencies — can start immediately
