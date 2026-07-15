# Session Time Analysis

## What This Angle Studies
When does this asset move? Classifies trading into 5 sessions (closed, london, ny_premarket, ny_regular, ny_afterhours) and analyzes session-level news correlation, price gaps, and news volume baseline.

## Results
5 sessions classified across 4 tickers, 962 session transitions each. Avg news volume: 1.8-2.0 articles/day. Premarket gaps: 0.6-4.0h. Session distribution: ny_regular=2244, ny_premarket=1605, ny_afterhours=1151 bars. Baseline API returns per-session z-scores. Gap API returns premarket gap hours.

## Execution Time
~65s (fetch 1h data + API calls)

### Bugs Found
- **Bug 1**: Correlation API missing session_correlations field — /correlation/{ticker} response lacks session_correlations key. API returns correlation=? with no session breakdown. Status: Open
- **Bug 2**: Correlation API returns sample_size=0 — All correlation values = 0 with sample_size=0. Data not pre-computed in correlation service. Status: Open