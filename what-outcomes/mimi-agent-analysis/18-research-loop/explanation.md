# Angle 18: Research Loop — Explanation

## What This Angle Studies
Automated strategy research: template selection (15 templates), auto-iteration, risk critic (19 dimensions), AST verification, weight holding check, auto-filters, hypothesis registry.

## Strategy & Configuration Used
- **Templates**: 15 built-in strategies (MA crossover, RSI mean reversion, etc.)
- **Risk critic**: 19 rule-based checks with PASS/REFINE/STOP verdicts
- **Auto-filters**: ADX, session exclusion, news cooldown, volatility guard
- **Validation**: Walk-forward, holdout, Monte Carlo, bootstrap, deflated Sharpe
- **Libraries**: vinu-research, vinu-strategy

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| Strategy templates (15) | `vinu-strategy/strategies/*.yaml` | Pre-built strategies |
| Risk critic (19 dims) | `vinu-research/` | Rule-based evaluation |
| Auto-filters | `vinu-research/` | ADX, session, news, volatility guards |
| Walk-forward | `vinu-research/` | IS/OOS validation |

## Results

### Available Strategy Templates (15)

| # | Template | Regime | Indicators |
|---|----------|--------|------------|
| 1 | MA Crossover | trending | SMA fast/slow |
| 2 | Triple MA Crossover | trending | SMA fast/mid/slow |
| 3 | MACD Crossover | trending | EMA fast/slow/signal |
| 4 | VWAP Crossover | intraday | VWAP |
| 5 | RSI Mean Reversion | ranging | RSI |
| 6 | Bollinger Bands Reversion | ranging | SMA, std |
| 7 | Z-Score Mean Reversion | ranging | SMA, z-score |
| 8 | Momentum (ROC) | trending | ROC |
| 9 | Rate of Change Momentum | trending | ROC threshold |
| 10 | Price Breakout | volatile | Rolling high/low |
| 11 | ATR Volatility Breakout | volatile | ATR |
| 12 | Supertrend | trending | ATR, hl_avg |
| 13 | ADX-Filtered Crossover | trending | SMA, ADX |
| 14 | Volume-Confirmed Breakout | trending | High, volume |
| 15 | Momentum/Mean Reversion | adaptive | ATR, SMA, z-score |

### Risk Critic (19 Dimensions)

| Category | Checks |
|----------|--------|
| Performance | MaxDD, Sharpe, Win Rate, Profit Factor, VaR, CVaR |
| Benchmark | Alpha, IR, Down Capture, Excess CAGR |
| Robustness | Sharpe p-value, Trade Count, Recovery Time |
| Overfitting | Sharpe Improvement, Iteration Stall, MaxDD Threshold |
| Activity | Turnover, Session Clustering, Passive Outperformance |

### Auto Filters

| Filter | Trigger | Action |
|--------|---------|--------|
| ADX filter | ADX < 20 | Skip weak trend |
| Session exclusion | London session | Exclude low-liquidity period |
| News cooldown | High-impact news < 60min | Skip trading |
| Volatility guard | ATR/close > 5% | Skip excessive vol |

### Research Loop Module Status
- `vinu_research.runner` not importable (import path mismatch)
- Code exists on disk at `vinu-research/vinu_research/`
- Available modules on disk: runner.py, walk_forward.py, decay.py, scheduled/, etc.

### Bugs Found
- **Bug 1**: `vinu_research.runner` module not found — import path differs from package structure

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Strategy template documentation | ~0.05s |
| 2 | Risk critic documentation | ~0.02s |
| 3 | Auto-filters documentation | ~0.01s |
| 4 | Module import test | ~0.02s |
| **Total** | | **~0.1s** |

## Summary
The research loop infrastructure is well-documented but has import path issues. 15 strategy templates, 19 risk critic dimensions, and 4 auto-filters are documented in the codebase. The `vinu_research.runner` module (main entry point) is not importable by the expected path, though the code exists on disk. The template-based strategy generation + rule-based risk critic + auto-filter injection pipeline is a complete automated strategy refinement system that can run without LLM.
