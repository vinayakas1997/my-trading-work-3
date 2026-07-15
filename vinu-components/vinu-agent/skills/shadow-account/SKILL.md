---
name: shadow-account
description: Trade journal backtesting pipeline - extract trades → simulate → render shadow P&L
category: tool
---

## Shadow Account Pipeline

### Pipeline Steps
1. **Extract Trades**: Parse trade confirmations, brokerage statements, or journal entries
2. **Normalize**: Convert to standard format (symbol, side, qty, price, timestamp, fees)
3. **Reconstruct**: Build position-level P&L from trade-level data
4. **Simulate**: Run what-if scenarios (different sizing, stops, holding periods)
5. **Render**: Generate shadow P&L report vs actual P&L

### Supported Input Formats
| Format | Source | Parser |
|--------|--------|--------|
| CSV | Generic brokerage export | Column mapping |
| PDF statement | Schwab, IBKR, Fidelity | PDF text extraction |
| Journal JSON | vinu-research | Native format |
| Manual entry | User chat | Structured prompt |

### Analysis Dimensions
- **Trade classification**: direction (long/short), asset class, sector, conviction (high/medium/low)
- **Timing analysis**: entry/exit quality relative to optimal signal
- **Sizing analysis**: optimal vs actual Kelly fraction
- **Behavioral scoring**: FOMO trades, revenge trades, hesitation cost

### Output Report
```
Shadow Account Summary — {period}
Actual P&L: +$X,XXX (+X.X%)
Shadow P&L: +$X,XXX (+X.X%)
Improvement Opportunity: +$X,XXX

Top 3 Leaks:
1. Exits too early (cost: $X,XXX)
2. Oversized losers (cost: $X,XXX)
3. Missed setups (opportunity: $X,XXX)
```
