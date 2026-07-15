---
name: factor-research
description: IC/IR evaluation, quantile backtesting, and factor combination methodology
category: analysis
---

## Factor Research Methodology

### Step 1: Factor Definition
Define the factor with a clear economic rationale:
- **Momentum**: Past returns predict future returns (short-term reversal or trending)
- **Value**: Undervalued assets outperform
- **Quality**: Profitable, stable companies outperform
- **Low Vol**: Low-beta assets deliver risk-adjusted outperformance

### Step 2: Information Coefficient (IC)
```python
ic = spearmanr(factor_values, forward_returns)
```
- Cross-sectional IC: Rank correlation at each time point
- Calculate daily/weekly IC values
- Report: mean IC, IC std, ICIR (IC / IC_std), t-stat

**Interpretation**:
- |IC| > 0.05: Meaningful signal
- ICIR > 0.3: Stable signal (IC is consistent)
- Positive IC: Factor predicts higher returns

### Step 3: Quantile Backtest
Split universe into 5 (or 10) quantiles each period:
```
Q1 (lowest factor) — expected to underperform
Q3 (middle) — neutral
Q5 (highest factor) — expected to outperform
```
- Calculate cumulative returns for each quantile
- Long Q5 / Short Q1 spread: should be positive and monotonic
- Monotonicity score: % of periods where returns follow factor order

### Step 4: Factor Combination
Combine uncorrelated factors for stronger signals:

**Simple equal-weight:**
```python
composite = zscore(factor_a) + zscore(factor_b)
```

**IC-weighted:**
```python
composite = ic_a * zscore(factor_a) + ic_b * zscore(factor_b)
```

**Guidelines**:
- Factor correlation should be < 0.3 for meaningful diversification
- Composite IC should exceed individual factor ICs
- Test on out-of-sample period before trusting

### Step 5: Robustness Checks
- Subperiod analysis: factor works in bull AND bear markets?
- Sector neutrality: remove sector bias from factor
- Size neutrality: remove market-cap bias
- Turnover analysis: how often does the factor flip positions?
