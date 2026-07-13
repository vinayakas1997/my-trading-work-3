# Phase 4: Advanced Portfolio & Risk Management (The Top 1% Features)

## The Problem
To elevate the system to institutional grade (top 1%), it must move beyond single-asset, fixed-size backtesting and slow, sequential evaluation. Real quant desks evaluate strategies across entire portfolios while dynamically managing risk and execution speed.

## How to Implement It

### 1. Vectorized and Parallel Execution
**Target Files:** `vinu-simulator/vinu_simulator/engine/simulator.py`, `vinu-research/vinu_research/llm_generator.py`

**Implementation Steps:**
- **Vectorized Backtests:** Replace the day-by-day `for` loop iteration (`.loc[date]`) in the simulator with vectorized `numpy` or `polars` operations. This allows the system to process years of data in milliseconds.
- **Concurrent LLM Generation:** Use `asyncio.gather` in the hybrid generator to request all 3 candidate strategies simultaneously from the LLM, reducing latency by 3x.

### 2. Portfolio-Level Backtesting & Beta Hedging
**Target Files:** `vinu-simulator/vinu_simulator/engine/portfolio_sim.py` (New Module)

**Implementation Steps:**
- Allow the strategy to ingest a universe of tickers (e.g., S&P 500) rather than a single asset.
- Track cross-asset correlation. 
- Automatically calculate the portfolio's Beta to the market. Implement an optional toggle for the system to automatically size a short index ETF position to maintain Beta neutrality (Market Neutral).

### 3. Dynamic Position Sizing (Kelly / Vol-Targeting)
**Target Files:** `vinu-simulator/vinu_simulator/engine/sizing.py` (New Module)

**Implementation Steps:**
- Move away from allocating 100% of capital to a single trade.
- **Volatility Targeting:** Scale position sizes inversely proportional to the asset's current ATR (Average True Range). If volatility spikes, position sizes shrink automatically.
- **Kelly Criterion:** Allow the LLM to output a confidence score, or calculate historical win rate / payoff ratio to dynamically size bets using fraction Kelly.

## Definition of Done
- The system can backtest a strategy against 100 tickers simultaneously in under 5 seconds.
- The generated report includes Portfolio Beta, Max Drawdown at the portfolio level, and verifies that the LLM generation phase is concurrent (evidenced by total runtime dropping significantly).
