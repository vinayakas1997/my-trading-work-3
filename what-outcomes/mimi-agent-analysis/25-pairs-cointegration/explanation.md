# ANGLE 25: Pairs Trading / Cointegration Analysis

## Status: NOT IMPLEMENTED

This angle is documented but **not yet implemented as a standalone module**. Currently exists only as LLM swarm preset prompts (`vinu-agent/swarm/presets/pairs_research_lab.yaml`, `statistical_arbitrage_desk.yaml`). No standalone executable code exists.

---

## What This Angle Would Study

**Question:** Are two assets statistically linked so that their price spread is mean-reverting and tradeable?

| Dimension | Description |
|-----------|-------------|
| Hedge ratio | OLS regression coefficient between two price series |
| Spread | Residual series: spread = asset_y - beta * asset_x |
| Stationarity (ADF) | Augmented Dickey-Fuller test — is the spread mean-reverting? |
| Cointegration (Johansen) | Johansen test — are assets cointegrated? |
| Half-life | Days until spread reverts 50% to mean |
| Z-score | Normalized spread for signal generation |
| Entry signals | Buy when z < -2.0, sell when z > +2.0 |
| Exit signals | Close when z returns to 0 |

---

## Planned Implementation

**Libraries needed:** `statsmodels`, `pandas`, `numpy` (all already in the project)

**Core functions to implement:**
```python
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.stattools import adfuller, coint

# 1. Hedge ratio
model = OLS(asset_y, asset_x).fit()
hedge_ratio = model.params[0]
spread = asset_y - hedge_ratio * asset_x

# 2. Stationarity test
adf_stat, adf_pvalue, _, _, _, _ = adfuller(spread)
is_stationary = adf_pvalue < 0.05

# 3. Cointegration test
coint_stat, coint_pvalue, _ = coint(asset_y, asset_x)
is_cointegrated = coint_pvalue < 0.05

# 4. Z-score signal
z_score = (spread - spread.mean()) / spread.std()
signal = "BUY" if z_score < -2.0 else "SELL" if z_score > 2.0 else "HOLD"
```

**Estimated effort:** Small (~50 lines of pure math)

---

## Future Work

- [ ] Implement standalone module in `vinu-correlation` or `vinu-research`
- [ ] Add API endpoint for pair analysis
- [ ] Add to agent tools
- [ ] Test across AAPL/MSFT, TSLA/NVDA pairs
- [ ] Add half-life calculation (Ornstein-Uhlenbeck)
- [ ] Add structural break detection
