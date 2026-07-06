# Chapter 10 — Granger causality test

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/engine/granger.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch08 |

## 1. Problem

Correlation does not imply causation. The Granger causality test asks: *does news volume help predict future price returns?* It tests whether lagged values of news volume significantly improve a forecast of returns.

## 2. Logic

Uses `statsmodels.tsa.stattools.granger_causalitytests` with `max_lag=12` (12 hours). Tests the null hypothesis that news does NOT Granger-cause returns.

```python
gct = grangercausalitytests(df[["returns", "news"]], max_lag, verbose=False)
```

## 3. Data contract

| Field | Type | Description |
|-------|------|-------------|
| `granger_causes_prices` | bool | True if best p-value < 0.05 |
| `best_lag_hours` | int | Lag with lowest p-value |
| `best_lag_minutes` | int | Same in minutes |
| `p_value` | float | Best (lowest) p-value across all lags |
| `test_results` | dict | Per-lag SSR F-test p-values |

## 4. Edge cases

- Requires at least `max_lag + 5` observations (17 hours)
- Returns safe defaults (no causation) on failure

## 5. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_granger.py` | Causality detection, edge cases with insufficient data |
