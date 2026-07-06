# Chapter 09 — Lag analysis

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/engine/correlation.py` (lag section) |
| **Status** | DRAFT |
| **Prerequisites** | ch08 |

## 1. Problem

News may affect prices with a delay. Lag analysis shifts the news series forward in time and recomputes correlation at each offset to find the best lead-lag relationship.

## 2. Logic

Default lags tested: **0, 15, 30, 60 minutes**.

For each lag, news timestamps are shifted backward by `lag_minutes`, then merged with return data and Pearson correlation is recomputed. The lag with the highest absolute correlation is reported as `best_lag_minutes`.

## 3. Data contract

| Field | Type | Example |
|-------|------|---------|
| `best_lag_minutes` | int | `30` |
| `best_lag_correlation` | float | `0.42` |
| `lag_results` | dict | `{"0m": 0.12, "15m": 0.35, "30m": 0.42, "60m": 0.28}` |

## 4. Edge cases

- Lag results for lags with < 3 merged data points are skipped
- Works best with at least 10+ hourly observations

## 5. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_correlation.py` | Lag results, best lag selection |
