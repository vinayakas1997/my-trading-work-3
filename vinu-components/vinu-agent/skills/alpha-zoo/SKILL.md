---
name: alpha-zoo
description: Reference guide to 461 pre-built alpha factors (qlib158, alpha101, GTJA191, academic, fundamental)
category: factor
---

## Alpha Zoo — Factor Categories

### Qlib158 Factors
Qlib's 158 hand-crafted factors from "Practical Guide to Quantitative Finance":
- **K-line factors**: derived from open, high, low, close, volume
- **VWAP factors**: volume-weighted average price relationships
- **Rank factors**: cross-sectional ranking transforms
- **Ref/Mean/Std/Corr operators**: time-series lookback computations

### Alpha101 Factors
101 formulaic factors from "101 Formulaic Alphas" by Zura Kakushadze:
- **Group A** (1-20): Short-horizon mean reversion and momentum
- **Group B** (21-60): Volatility-adjusted and combination factors
- **Group C** (61-101): Complex multi-step interactions
- Formula: `rank(ts_argmax(power(((returns < 0) ? std(returns, 20) : close), 2.0), 5))`

### GTJA191 Factors
191 factors from Guotai Junan Securities:
- **Momentum** (3-30): Price trend and acceleration
- **Value** (31-60): Earnings yield, book-to-price, cash-flow yield
- **Growth** (61-90): Earnings and revenue growth rates
- **Quality** (91-120): ROE, profit margins, earnings stability
- **Technical** (121-160): Volume, volatility, turnover patterns
- **Sentiment** (161-191): Analyst revisions, insider trading, short interest

### Academic Factors
Well-documented cross-sectional factors:
- Size (market cap), Value (B/P, E/P), Momentum (12-1), Reversal (1m)
- Quality (ROE, gross margins, accruals), Low Vol (beta, IVOL)
- Investment (asset growth, NOA), Profitability (GP/A, ROIC)

### Usage
- IC/IR evaluation via `factor-research` skill
- Factor combination via `multi-factor` skill
- Zoo located in `vinu-features/zoo/`
