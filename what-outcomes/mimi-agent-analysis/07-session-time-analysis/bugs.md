# Session Time Analysis — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | Correlation API missing session_correlations field | /correlation/{ticker} response lacks session_correlations key | API returns correlation=? with no session breakdown | Open |
| 2 | Correlation API returns sample_size=0 | All correlation values = 0 with sample_size=0 | Data not pre-computed in correlation service | Open |
