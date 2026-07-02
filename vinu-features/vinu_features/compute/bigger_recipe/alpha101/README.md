# alpha101

## Why use it

- **Quant factor research** — 101 formulaic alphas (WorldQuant-style) for ML and systematic screens.
- Rich non-linear feature pool beyond classical TA — ranks, correlations, rolling stats.
- Cross-sectional and time-series research when paired with a universe of symbols.

## What it is

- **WorldQuant 101 alphas** — expression-evaluated factor columns `ALPHA101_001` … `ALPHA101_101`.
- Mix of handcrafted formulas (first 10) and templated ROC/MA/STD/RANK/CORR/RSV families.
- **Recipe name:** `alpha101` | **Warmup:** 60 bars | **Feature count:** 101
- Engine: `bigger_recipe/_alpha_expr/evaluator.py`

## How to use it

**Not for discretionary single-factor trading in v1.** Typical workflow:

1. Request `alpha101` on a universe → `features.parquet`
2. Rank or z-score factors cross-sectionally per day (see `ml_models/normalize/README.md`)
3. Train booster model (`xgboost`, `lightgbm`) on `forward_return_1` or `forward_return_5` labels
4. Walk-forward validate — avoid in-sample overfitting

**Factor families (high level):**

| Family | Examples | Intuition |
|---|---|---|
| Rank | `Rank($close, 20)` | Relative position in recent window |
| Correlation | `Corr($close, $volume, d)` | Price–volume relationship |
| ROC / MA / STD | Lag returns, mean ratios | Momentum and volatility shape |
| RSV | Stochastic-like range position | Mean-reversion pressure |

## Caveats

- 101 features vs limited history → overfitting risk without regularization and walk-forward tests.
- Adapted for single-symbol time series here; true WorldQuant alphas are cross-sectional.
- Do not interpret each `ALPHA101_XXX` individually without research — use ML aggregation.
- Lookahead and survivorship bias in research are your responsibility.

## Market notes

- **A — Generic daily equities:** Academic and buy-side factor research standard.
- **B — India (NSE/BSE):** Apply liquidity filters (Nifty 500) before factor mining; thin names distort rank factors.
- **C — US equities:** Large universes (Russell 1000) suit cross-sectional rank; align with Qlib/WorldQuant literature.

## In this codebase

- Path: `bigger_recipe/alpha101/alpha101.py`
- Request recipe: `alpha101`
- Expression engine: `bigger_recipe/_alpha_expr/evaluator.py`
