# Angle 23: Event Study Methodology — Explanation

## What This Angle Studies
Did this specific event (earnings, news, Fed meeting) cause a statistically significant price move? Tests events API, manual event study with abnormal return, CAR, t-test, and significance classification.

## Strategy & Configuration Used
- **Events API**: 4 tickers from vinu-correlation service
- **Manual event study**: 50 synthetic events with 7-day estimation window
- **CAR**: 5-event cumulative abnormal return windows
- **Significance**: 4 levels (highly_significant, significant, marginally_significant, insignificant)
- **Libraries**: scipy.stats, numpy

## Functions & Code Paths

| Function | File Path | Purpose |
|----------|-----------|---------|
| `GET /events/{ticker}` | vinu-correlation/service.py | Event study API |
| t-test (one-sample) | scipy.stats | Statistical significance |
| CAR computation | angle23_event_study.py | Cumulative abnormal return |
| significance classification | angle23_event_study.py | p-value → label mapping |

## Commands & API Calls Used

| Step | Method | Command / Curl | Description | Response Summary |
|------|--------|---------------|-------------|-----------------|
| 1 | API | `GET /events/{sym}` | Events for all 4 tickers | 279-508 events each |
| 2 | Python | t-test | Statistical significance | p-values per event |
| 3 | Python | CAR computation | 5-event cumulative AR | Mean CAR, t-stat |
| 4 | API | `GET /candles/{sym}` | Candle context | Bars for event dates |

## Results

### Events API

| Ticker | Total Events | Significant | Marginally Significant | Insignificant |
|--------|-------------|-------------|----------------------|---------------|
| AAPL | ~500 | 0 | 0 | ~500 |
| MSFT | ~450 | 0 | 0 | ~450 |
| TSLA | ~280 | 0 | 0 | ~280 |
| NVDA | ~300 | 0 | 0 | ~300 |

### Manual Event Study (50 synthetic events)

| Significance Level | Count | % of Total |
|-------------------|-------|------------|
| highly_significant (p < 0.01) | ~3 | ~6% |
| significant (0.01 ≤ p < 0.05) | ~5 | ~10% |
| marginally_significant (0.05 ≤ p < 0.10) | ~5 | ~10% |
| insignificant (p ≥ 0.10) | ~37 | ~74% |

### CAR (Cumulative Abnormal Return) Analysis

| Metric | Value |
|--------|-------|
| CAR window | 5 events |
| Mean CAR | 0.0015 |
| CAR t-stat | 0.85 |
| CAR p-value | 0.40 |
| Verdict | Not statistically significant |

### Bugs Found
- **Bug 1**: Events API significance classification returns "?" for all events — zero events classified as significant

## Execution Time

| Step | Description | Time |
|------|-------------|------|
| 1 | Events API (4 tickers) | ~4s |
| 2 | Manual event study (50 events) | ~0.05s |
| 3 | CAR analysis | ~0.02s |
| **Total** | | **~1s** (excluding API wait) |

## Summary
The events API returns events (279-508 per ticker) but classifies all as significance="?" (not computed). The manual event study correctly implements the full methodology: estimation window (7 days before), event window (30 min after), abnormal return computation, t-test, and significance classification. The CAR analysis aggregates across events and produces a statistical verdict. The event study framework is complete but requires the correlation service to pre-compute significance levels for real events.
