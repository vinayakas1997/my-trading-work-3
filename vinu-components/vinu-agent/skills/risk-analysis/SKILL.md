---
name: risk-analysis
description: Portfolio risk assessment including VaR, stress testing, correlation analysis, and risk budgeting
category: risk
---

## Risk Analysis Framework

### Risk Types

| Type | Source | Measurement |
|------|--------|-------------|
| Market Risk | Price movements | VaR, Beta, Greeks |
| Liquidity Risk | Cannot trade at fair price | Bid-ask spread, volume profile |
| Concentration Risk | Single name/country exposure | Herfindahl-Hirschman Index |
| Tail Risk | Extreme events beyond 3-sigma | CVaR, expected shortfall |
| Model Risk | Wrong assumptions | Backtest OOS deterioration |
| Operational Risk | System/process failure | Error rate, downtime |

### Correlation Analysis
- Rolling 60-day correlation matrix
- Regime-dependent correlations (bull vs bear markets)
- Correlation breakdown during crises (all correlations → 1)

### Risk Budgeting
1. Define total risk budget (e.g., 15% annual vol)
2. Allocate across asset classes by risk contribution
3. Marginal risk contribution = position weight × covariance with portfolio
4. Risk parity: equal risk contribution from each asset

### Stress Scenarios
| Scenario | Shock | Typical Impact |
|----------|-------|----------------|
| 2008-style | Equities -50%, HY spreads +1000bp | Long equity, short vol crushed |
| 2020 COVID | Equities -30%, rates -100bp | All risk assets drop |
| 2022 Inflation | Rates +300bp, equities -20% | Long duration, growth stocks hurt |
| Rate Shock | Rates +100bp in 1 month | Bond and equity correlation → positive |
