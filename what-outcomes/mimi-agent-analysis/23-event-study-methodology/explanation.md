# Event Study Methodology

## What This Angle Studies
Tests event study: 7-day estimation window, 30-min event window, abnormal return, CAR, t-test for significance.

## Results
Event study API works: AAPL=367 events, MSFT=279, TSLA=313, NVDA=508. Events include headline, sentiment, price deltas. However, 0 events classified as significant (significance field="?"). Manual event study (Fed meeting 2022-03-16) computes abnormal return correctly.

## Execution Time
~1s

### Bugs Found
- **Bug 1**: Events API returns 0 significant events — All events have significance="?". Significance field not populated - t-test may not be computed or significance threshold not met. Status: Open