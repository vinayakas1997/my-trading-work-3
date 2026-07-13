# alpha360

## Why use it

- **Deep price history as features** — 60 lags of normalized OHLCV + VWAP for sequence-aware ML.
- Neural nets and gradient boosting can learn patterns from raw lag structure without hand-crafted factors.
- Qlib Alpha360DL port — standard when history shape matters more than named indicators.

## What it is

- **qlib Alpha360 normalized OHLCV** — 360 columns: 6 fields × 61 lags (59…0).
- Each value is ratio-normalized (e.g. `Ref($close, i)/$close`, `Ref($volume, i)/$volume`).
- Fields: **CLOSE**, **OPEN**, **HIGH**, **LOW**, **VWAP**, **VOLUME**
- **Recipe name:** `alpha360` | **Warmup:** 60 bars | **Feature count:** 360

**Column naming:** `CLOSE59` … `CLOSE0` (0 = today), then `OPEN*`, `HIGH*`, `LOW*`, `VWAP*`, `VOLUME*`.

## How to use it

1. Request `alpha360` when training ML models that need long lookback (LSTM planned outside v1; boosting works now).
2. Combine with `xgboost` / `lightgbm` and forward return labels.
3. Expect large `features.parquet` — monitor memory on wide universes.
4. Compare model lift vs `alpha158` (hand-crafted) vs `full_ta` (TA).

**Interpretation:** Individual lag columns are not chart indicators — the model learns weights across the 360-dimensional snapshot.

## Caveats

- 360 features + short history = severe overfitting without regularization and walk-forward validation.
- Normalization is per-field ratio — not cross-sectional z-score across universe.
- Not for discretionary trading rules on single lag columns.
- Requires 60+ bars warmup before valid feature rows.

## Market notes

- **A — Generic daily equities:** Used in Qlib ML pipelines for daily alpha forecasting.
- **B — India (NSE/BSE):** Volume lag ratios sensitive to block deals; filter events or winsorize in research.
- **C — US equities:** Stock splits must be adjusted in source OHLCV or lag ratios break.

## In this codebase

- Path: `bigger_recipe/alpha360/alpha360.py`
- Request recipe: `alpha360`
- VWAP field ties to `indicators/vwap/README.md` (cumulative implementation in engine)
- Expression engine: `bigger_recipe/_alpha_expr/evaluator.py`
