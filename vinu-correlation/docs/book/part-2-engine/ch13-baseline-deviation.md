# Chapter 13 — Baseline & news volume deviation

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/engine/baseline.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch14 |

## 1. Problem

Is the current news volume normal, elevated, or critical for a given ticker? Baseline computes a rolling average and standard deviation of news volume per market session, then classifies the current observation by z-score.

## 2. Logic

For each hour and session, the baseline for the current hour is:

- **Mean**: average article count over the trailing `window_days` (default 7)
- **Stddev**: sample standard deviation over the same window
- **Z-score**: `(current_count - mean) / stddev`
- **Deviation level**: classified by abs(z-score)

## 3. Deviation levels

| Z-score range | Label |
|---------------|-------|
| abs(z) <= 2 | normal |
| 2 < abs(z) <= 3 | elevated |
| 3 < abs(z) <= 4 | high |
| abs(z) > 4 | critical |

## 4. Data contract

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | str | Ticker symbol |
| `mean_daily_articles` | float | Avg articles/day across all sessions |
| `sessions` | dict | Per-session breakdown |
| `→ {session}.mean` | float | Mean article count per hour |
| `→ {session}.stddev` | float | Stddev of article count |
| `→ {session}.z_score` | float | Current z-score |
| `→ {session}.deviation_level` | str | normal/elevated/high/critical |

## 5. Tests

| Test file | Asserts |
|-----------|---------|
| `tests/test_baseline.py` | Baseline calculation, deviation classification |
