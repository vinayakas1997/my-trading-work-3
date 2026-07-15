# Event Study Methodology — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | Events API returns 0 significant events | All events have significance="?" | Significance field not populated - t-test may not be computed or significance threshold not met | Open |
