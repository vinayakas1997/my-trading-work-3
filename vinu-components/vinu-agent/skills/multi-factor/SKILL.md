---
name: multi-factor
description: Factor combination, weighting, and portfolio construction methodology
category: factor
---

## Multi-Factor Framework

### Factor Combination Methods

| Method | Use Case | Strength |
|--------|----------|----------|
| Equal Weight | No prior knowledge | Simple, robust |
| IC-Weighted | Historical IC known | Higher expected return |
| Rank-Based | Non-normal IC distribution | Outlier resistant |
| ML-Weighted | Complex non-linear interactions | Highest potential, overfitting risk |
| PCA | Factors are highly collinear | Orthogonal, interpretable |

### Score Normalization
```
z-score = (raw_score - mean) / std
rank_pct = rank(raw_score) / N
winsorized = clip(raw_score, p1, p99)
```

### Portfolio Construction

#### Long-Short
- Top decile → long, bottom decile → short
- Market-neutral: beta-neutral, sector-neutral, dollar-neutral
- Leverage: 2x-3x gross exposure typical

#### Long-Only
- Top quintile equal-weighted or cap-weighted
- Benchmark-relative: active weights = factor weight - benchmark weight
- Turnover control: 20-30% monthly maximum

### Factor Monitoring
- **IC decay**: if IC < 0.02 for 3 months, review/replace
- **Factor crowding**: increasing cross-sectional correlation → reduce weight
- **Regime dependency**: momentum fails in reversals, value fails in late cycles
