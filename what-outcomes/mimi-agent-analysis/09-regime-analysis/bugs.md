# Regime Analysis — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | Regime Sharpe values are unrealistically extreme | Bull regime Sharpe ~37, Bear regime ~-36 | Regime definition uses contemporaneous returns: a +1% day IS a bull day by definition, so within-regime Sharpe amplifies the classification itself | Design limitation |
