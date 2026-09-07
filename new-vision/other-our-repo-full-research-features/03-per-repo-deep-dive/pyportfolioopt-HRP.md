# Deep Dive — robertmartin8/PyPortfolioOpt (~3.4K stars)

> Source: `https://github.com/robertmartin8/PyPortfolioOpt` + cookbook.

## What to look at

- `pypfopt/efficient_frontier.py` — `EfficientFrontier.max_sharpe()`.
- `pypfopt/hrp.py` — Hierarchical Risk Parity.
- `pypfopt/black_litterman.py` — BL views.
- `pypfopt/objective_functions.py` — `L2_reg(gamma=0.1)`.

## Install & spike

```bash
pip install PyPortfolioOpt
python -c "from pypfopt import EfficientFrontier; help(EfficientFrontier)"
```

## Extractable for Vinu

1. **HRP** → replace provisional `fractional_kelly` `config.py:106` with HRP for `compute_daily_allocation` (pending Row 5). Best for no-return-estimate regime.
2. **L2_reg** → `ef.add_objective(objective_functions.L2_reg, gamma=0.1)` de-concentrates weights — directly addresses composition view Row 4.
3. **Black-Litterman** → if you add `Thesis Intake` views as BL views.

## Cookbook

- `cookbook/` notebooks — copy pattern for `vinu-portfolio/service.py:build_portfolio` test.
