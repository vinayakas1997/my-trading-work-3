---
name: valuation-model
description: Equity valuation models - DCF, multiples, LBO, sum-of-the-parts, and relative value
category: fundamental
---

## Valuation Models

### DCF (Discounted Cash Flow)
```
Enterprise Value = Sum(FCF_t / (1 + WACC)^t) + Terminal Value / (1 + WACC)^n
Terminal Value = FCF_n * (1 + g) / (WACC - g)
Equity Value = EV - Net Debt
```
**Sensitivities**: WACC ± 1%, terminal growth ± 0.5%

### Trading Comps
| Multiple | Sector | Pitfall |
|----------|--------|---------|
| P/E | All sectors | Earnings manipulation |
| EV/EBITDA | Capital-intensive | Ignores capex needs |
| P/B | Financials | Intangible-heavy firms |
| EV/Sales | Growth/Pre-profit | Ignores margin |
| FCF Yield | Mature/generating FCF | Cyclical distortion |

### SOTP (Sum of the Parts)
```
Fair Value = Sum(Division_i × Multiple_i) - Corporate Costs
```
- Use for conglomerates with disparate business lines
- Conglomerate discount: 10-20% for holding company structure

### LBO Model
- Entry multiple, exit multiple, debt capacity, IRR calculation
- Key metric: MOIC (multiple on invested capital) > 2.5x
- Debt paydown drives returns in early years, multiple expansion in later years

### Common Pitfalls
- Terminal value > 80% of DCF value → check assumptions
- Using forward P/E without earnings quality adjustment
- Ignoring off-balance-sheet items (leases, pension deficits)
- Not normalizing earnings for cyclical companies
