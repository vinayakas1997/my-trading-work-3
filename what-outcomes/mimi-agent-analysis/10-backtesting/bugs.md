# Backtesting — Bugs

| # | Bug | Error | Root Cause | Status |
|---|-----|-------|------------|--------|
| 1 | Simulator API returns 422 on simulate | No weight data found for strategy | Strategy must be evaluated first via vinu-strategy before simulator can run. No strategy data pre-computed. | Open |
| 2 | No HTTP endpoint for strategy registration | Cannot POST new strategy YAML | Strategies are loaded from filesystem only; no API for dynamic registration | Design |
