---
name: quant-statistics
description: Statistical methods for quantitative finance including hypothesis testing, time-series analysis, and risk metrics
category: quant
---

## Quant Statistics Reference

### Hypothesis Testing in Finance

| Test | Null | Use When |
|------|------|----------|
| t-test | mean return = 0 | Single strategy returns |
| Welch t-test | means equal | Comparing two strategies |
| Jarque-Bera | normal distribution | Return normality check |
| ADF Test | unit root exists | Stationarity of price series |
| Engle-Granger | no cointegration | Pairs trading candidates |
| Ljung-Box | no autocorrelation | Residual independence |

### Time-Series Models

#### ARIMA(p,d,q)
- p: autoregressive lags (PACF cutoff)
- d: differencing order (ADF test)
- q: moving average lags (ACF cutoff)

#### GARCH(1,1)
```
sigma²_t = omega + alpha * eps²_{t-1} + beta * sigma²_{t-1}
```
- alpha: reaction to new information
- beta: persistence of volatility
- alpha + beta < 1 for stationarity

### Risk Metrics

| Metric | Formula | Interpretation |
|--------|---------|----------------|
| VaR (95%) | percentile(returns, 5) | Max loss with 95% confidence |
| CVaR | mean(returns < VaR) | Expected tail loss |
| Semi-Deviation | std(min(returns, 0)) | Downside volatility |
| Omega Ratio | mean(gains) / mean(losses) | Gain/loss asymmetry |
| Calmar Ratio | CAGR / MaxDD | Return relative to max drawdown |

### Bootstrapping
- Randomize entry times (preserve return distribution)
- Block bootstrap (preserve autocorrelation structure)
- Monte Carlo of HFT strategies with microsecond randomization
