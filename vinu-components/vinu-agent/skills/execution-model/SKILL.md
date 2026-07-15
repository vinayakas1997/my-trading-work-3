---
name: execution-model
description: Slippage models, VWAP/TWAP, and cost tables for realistic backtests
category: strategy
---

## Execution Models

### Slippage Models

**Fixed Slippage** — Simplest, use for liquid large-caps:
```python
slippage = 0.001  # 0.1% per share
```

**Linear Slippage** — Scales with trade size relative to volume:
```python
slippage = 0.0005 * (trade_volume / avg_daily_volume)
```

**Square-Root Slippage** — Empirical market impact model (Almgren-Chriss):
```python
slippage = 0.0001 + 0.0002 * sqrt(trade_volume / avg_daily_volume)
```

### VWAP/TWAP Models

**TWAP** — Slice order evenly over time:
- Divide total quantity into N equal tranches
- Execute one tranche per time interval
- Use for: low-urgency, low-alpha strategies

**VWAP** — Slice proportional to expected volume profile:
- Front-load during high-volume periods
- Back-load during low-volume periods
- Use for: high-urgency, high-alpha strategies

### Cost Tables

| Market Cap | Fixed Slippage | Market Impact | Commission |
|-----------|----------------|---------------|------------|
| Mega (>200B) | 0.05% | 0.02% | $0.003/share |
| Large (10-200B) | 0.10% | 0.05% | $0.005/share |
| Mid (2-10B) | 0.20% | 0.10% | $0.008/share |
| Small (<2B) | 0.50% | 0.30% | $0.015/share |

### Integration
When running `vinu-simulator` backtests:
1. Set `slippage_model` to one of: `fixed`, `linear`, `sqrt`
2. Set `slippage_params` based on asset class
3. Apply cost table when comparing across market caps
4. Always run sensitivity: double slippage, verify strategy still profitable
