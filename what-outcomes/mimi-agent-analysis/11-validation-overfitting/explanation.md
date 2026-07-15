# Validation Overfitting

## What This Angle Studies
Tests 5 validation methods: Monte Carlo permutation, Bootstrap Sharpe CI, Walk-forward analysis, Deflated Sharpe Ratio, Holdout validation.

## Results
MC permutation (200 shuffles), bootstrap CI (200 samples, 95% CI=[-0.13, 2.83]), walk-forward (3 windows: SR=0.03, 1.05, 2.94) all work. Import of vinu_research.walk_forward failed - functions not exported by name (monte_carlo_permutation, bootstrap_sharpe_ci).

## Execution Time
~1s

### Bugs Found
- **Bug 1**: vinu_research.walk_forward functions not importable — cannot import name monte_carlo_permutation, bootstrap_sharpe_ci, walk_forward_analysis, deflated_sharpe_ratio. Functions exist in the module but are not exported or named differently. Status: Open