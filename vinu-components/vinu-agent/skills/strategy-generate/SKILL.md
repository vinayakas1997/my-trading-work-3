---
name: strategy-generate
description: 7-step strategy development workflow with SignalEngine contract
category: strategy
---

## Strategy Generation — 7-Step Workflow

### Step 1: Define Hypothesis
State your trading edge clearly:
- What market condition does this exploit?
- What is the entry signal?
- What is the exit condition?
- Is this mean-reversion, momentum, or breakout?

### Step 2: Choose Signal Engine
Select your signal type:
- **Crossover** — Two lines crossing (e.g., SMA cross, MACD)
- **Threshold** — Single indicator above/below a level
- **Composite** — Multi-condition boolean logic
- **ML Signal** — Model output as signal

### Step 3: Configure Parameters
```yaml
signal:
  type: crossover  # crossover | threshold | composite | ml
  fast: sma_20
  slow: sma_50
filters:
  - name: volume_min
    operator: gt
    value: 1000000
  - name: adx_filter
    operator: gt
    value: 25
```

### Step 4: Run Initial Backtest
- Use `vinu-simulator` with `CustomSimulateRequest`
- Default parameters: `sma_20`, `sma_50`, `rsi_14`
- Run on at least 2 years of 1D data
- Check basic metrics: Sharpe > 1.0, MaxDD < 30%

### Step 5: Diagnose Failures
If the backtest fails, use `load_skill("backtest-diagnose")` to debug:
- Error type (no trades, poor Sharpe, high drawdown)
- Apply the hard-gate checklist

### Step 6: Refine
Iterate on parameters one at a time:
- Change only 1 parameter per iteration
- Document each variant's impact
- Test on out-of-sample period (last 20% of data)

### Step 7: Document
Record the final strategy with:
- Hypothesis, parameters, performance table
- OOS metrics
- Known failure modes
