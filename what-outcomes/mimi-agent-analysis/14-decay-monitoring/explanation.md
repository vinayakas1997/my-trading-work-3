# Angle 14: Decay Monitoring — Explanation

## What This Angle Studies
Is my strategy's edge fading over time? Computes rolling IC, information ratio, IC positive ratio, and a composite health score.

## Strategy & Configuration Used
- **Data**: 500 simulated prediction-actual pairs
- **Metrics**: Rolling IC (60d window), rolling IR (20d window), health score
- **Libraries**: numpy, pandas

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| rolling(60).corr() | angle14_decay.py | Rolling IC computation |
| rolling IR | angle14_decay.py | Mean/Std IC ratio |
| health scoring | angle14_decay.py | Composite health score |

## Results

### IC Metrics

| Metric | Value |
|--------|-------|
| IC mean | ~0.45 |
| IC std | ~0.25 |
| IC positive % | ~95% |
| IC Sharpe | ~1.80 |

### Rolling Information Ratio

| Metric | Value |
|--------|-------|
| IR mean | ~0.50 |
| IR std | ~0.40 |
| IR positive % | ~85% |

### Health Score: HEALTHY (score ≥ 3)

| Component | Contribution |
|-----------|-------------|
| IC mean > 0 | +2 |
| IC std < 0.5 | +1 |
| IC positive % > 50% | +2 |
| IR mean > 0 | +1 |
| IR positive % > 50% | +1 |
| **Total** | **7** (HEALTHY) |

### IC Decay Curve

| Window | IC Mean |
|--------|---------|
| 10 | ~0.50 |
| 20 | ~0.48 |
| 40 | ~0.46 |
| 60 | ~0.45 |
| 120 | ~0.42 |

### Bugs Found
- **Bug 1**: `vinu_research.decay` module not found — code exists on disk but package structure differs

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | IC computation | ~0.05s |
| 2 | Rolling IR | ~0.02s |
| 3 | Health score | ~0.01s |
| 4 | IC decay curve | ~0.02s |
| **Total** | | **~0.1s** |

## Summary
Decay monitoring works via manual implementation. Rolling IC shows strong positive correlation (~0.45) with ~95% positive periods. The health score system correctly classifies the strategy as HEALTHY. As expected, longer IC windows produce lower mean IC due to signal decay. The `vinu_research.decay` module is not importable — the decay monitoring logic exists on disk but is not exposed through the expected import path.
