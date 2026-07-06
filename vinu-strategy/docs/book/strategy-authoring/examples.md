# Strategy Examples

## Overview

This document provides complete, working examples of common trading strategies.

## Example 1: Simple MA Crossover

**Description**: Buy when 9-day SMA crosses above 21-day SMA.

```yaml
name: ma_crossover
description: "9/21 SMA crossover strategy"
schedule: daily
features_required:
  - sma_9
  - sma_21
pipeline:
  selection:
    method: all
  allocation:
    method: signal_scaled
    signal: "sma_9 / sma_21 - 1"
  timing:
    method: none
  risk:
    method: normalize
    max_weight: 0.25
    cash_floor: 0.10
```

**Behavior**:
- Long when SMA_9 > SMA_21
- Short when SMA_9