---
name: options-trading
description: Options pricing, Greeks, strategies, and risk management
category: derivatives
---

## Options Trading Reference

### Pricing Models
| Model | Use Case | Inputs |
|-------|----------|--------|
| Black-Scholes | European options | S, K, T, r, σ, q |
| Binomial Tree | American options | Same + early exercise |
| Monte Carlo | Path-dependent (barrier, Asian) | Simulated paths |

### Greeks
| Greek | Definition | Interpretation |
|-------|------------|----------------|
| Delta (Δ) | dPrice / dUnderlying | Directional exposure (-1 to 1) |
| Gamma (Γ) | dDelta / dUnderlying | Delta acceleration (highest ATM) |
| Theta (Θ) | dPrice / dTime | Time decay (negative for long options) |
| Vega (ν) | dPrice / dVol | Volatility exposure |
| Rho (ρ) | dPrice / dRate | Interest rate sensitivity |

### Common Strategies

| Strategy | Outlook | Risk | Max Profit |
|----------|---------|------|------------|
| Long Call | Bullish | Premium paid | Unlimited |
| Long Put | Bearish | Premium paid | Strike - premium |
| Covered Call | Neutral-bullish | Stock declines | Premium + stock gain |
| Iron Condor | Low volatility | Width of wings | Net credit received |
| Straddle | High volatility | Premium paid | Unlimited (one side) |

### Risk Rules
- Single option position < 5% of portfolio
- Net delta exposure within ±20% of notional
- No naked short options without collateral
- Position limit: 25% of open interest
- IV rank > 80% → prefer credit spreads (sell premium)
- IV rank < 20% → prefer debit spreads (buy premium)
