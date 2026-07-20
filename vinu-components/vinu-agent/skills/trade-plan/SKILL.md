---
name: trade-plan
description: Generate a granular staged trading plan from existing analysis, signals, and backtest validation — no broker execution
category: analysis
---

## Trade-Plan Generation — Methodology

This skill generates a **forward-looking trading plan document** (entry conditions, profit-booking tranches, invalidation/exit rules) from existing analysis data. Output is a human-readable report — no orders are submitted.

### Data Tiers

The plan is built from up to three tiers (tier 4 — ML model score — is deferred):

1. **Structural/contextual** — Market-structure angles from `initial-analysis-api`:
   - `trend_lifecycle` — trend stage and risk regime
   - `trend_session_structure` — intraday session structure
   - `regime_analysis` — broader market regime
   - `drawdown_deep_dive` — drawdown context (for invalidation logic)
   - `news_price_causality` — news-driven vs technical moves
2. **Quantitative signal** — Computed factors/indicators from `vinu-tools`:
   - Use a timeframe-appropriate preset recipe (e.g. `trend_pack` for trend-following, `alpha158` for broad factor read)
   - Real computed values via `POST /requests` with `run_immediately=true`
3. **Statistical confidence** — Monte Carlo p-value from `vinu-simulator` if a matching backtest artifact exists for the symbol:
   - `monte_carlo_permutation` p-value (null: random trade ordering is no better)
   - Bootstrap Sharpe confidence interval
   - Walk-forward consistency rate

### Plan Structure

The generated plan must contain three sections:

#### A. Entry Checklist
- Conditions that must ALL be true before entering:
  - Trend direction alignment (from `trend_lifecycle` stage)
  - Session structure conformation (from `trend_session_structure`)
  - Signal confirmation from quantitative factors (tier 2)
  - Volume/volatility filters
- Each condition gets a status: MET | NOT MET | PENDING

#### B. Staged Profit-Booking Tranches
- Split the position into 2–3 tranches based on trend strength:
  - Strong trend (aggressive): 50/30/20 split
  - Moderate trend (balanced): 40/30/30 split
  - Weak/no trend (conservative): 33/33/34 split
- Each tranche specifies:
  - Target price or R-multiple (e.g. 1.5R, 2.5R, 4R)
  - Fraction of position to close
  - Trailing stop trigger (optional, for remaining position)

#### C. Invalidation / Exit Checklist
- Conditions that trigger exit, reduce, or hold decisions:
  - **Hard exit**: Stop-loss hit, trend reversal signal, gap against position
  - **Reduce**: Partial invalidation, regime change, volatility spike
  - **Hold**: Drawdown within expected range, no new signal
- Each condition has an explicit action: EXIT | REDUCE | HOLD

### Timeframe Selection

The timeframe parameter determines which angles are relevant:
- **Intraday / 15-min**: `trend_session_structure` (primary), `trend_lifecycle`, `regime_analysis`
- **Daily / Swing**: `trend_lifecycle` (primary), `regime_analysis`, `drawdown_deep_dive`
- **Weekly / Position**: `drawdown_deep_dive` (primary), `regime_analysis`, `trend_lifecycle`

### Usage

```python
from vinu_agent.tools.trade_plan_tool import TradePlanTool

tool = TradePlanTool()
tool._services_config = {"vinu_initial_analysis": "http://localhost:8083", ...}
result = tool.execute(symbol="AAPL", timeframe="daily")
```
