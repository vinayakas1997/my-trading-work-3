# alpha158

## Why use it

- **Qlib Alpha158 factor set** — 158 engineered features for ML-based alpha research.
- Broader than `full_ta`: candlestick shapes (KMID, KLEN), rolling betas, volume correlations, count stats.
- Standard preset when porting Qlib pipelines or training gradient boosting on rich factor matrices.

## What it is

- **qlib Alpha158 factors** — columns like `KMID`, `ROC5`, `MA20`, `STD20`, `CORR20`, `VSUMP20`, etc.
- **Recipe name:** `alpha158` | **Warmup:** 60 bars | **Feature count:** 158
- Config excludes cross-sectional `RANK` rolling ops (time-series adapted); see `alpha158.py` `get_feature_config()`

**Factor families:**

| Family | Prefix examples | Intuition |
|---|---|---|
| K-bar | KMID, KLEN, KUP, KLOW, KSFT | Candlestick geometry vs range |
| Price / volume lags | OPEN0, HIGH0, VOLUME1 | Normalized level vs close |
| Rolling ROC/MA/STD | ROC10, MA30, STD60 | Momentum and volatility |
| Correlation | CORR20, CORD20 | Price–volume linkage |
| Count / sum | CNTP20, SUMP20, VSUMP20 | Up-day fraction, signed move sums |

## How to use it

1. Request `alpha158` on symbol history (60+ warmup bars)
2. Pair with `ml_models` (`lightgbm`, `xgboost`) and `forward_return_5` label
3. Feature importance / SHAP to see which families matter (post-training)
4. Compare against `full_ta` (31 cols) for lift vs complexity

**Not for:** Reading each of 158 columns on a chart — this is an ML feature matrix.

## Caveats

- High dimensionality → strict train/test discipline required.
- Single-symbol mode ≠ full Qlib cross-sectional pipeline.
- RANK factors excluded by config — cross-sectional rank must be done in your research layer.

## Market notes

- **A — Generic daily equities:** Qlib research standard on daily bars.
- **B — India (NSE/BSE):** Validate factors on liquid universes; corporate actions affect K-bar ratios.
- **C — US equities:** Common in quant shop Qlib workflows; watch ADR vs common share data alignment.

## In this codebase

- Path: `bigger_recipe/alpha158/alpha158.py`
- Request recipe: `alpha158`
- Expression engine: `bigger_recipe/_alpha_expr/evaluator.py`
