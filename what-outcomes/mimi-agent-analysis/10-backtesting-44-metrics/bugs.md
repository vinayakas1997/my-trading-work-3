# Bugs Found: Angle 10 — Backtesting (44+ Metrics)

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Simulator API returns 422 on POST /simulate | HTTP 422 with weight data error | No weight data pre-computed in simulator service | None | vinu-simulator | High | Open |
| 2 | Strategy evaluate endpoint returns 500 | HTTP 500 — Internal Server Error | Two-root cause: (a) Strategy service not started with strategies dir, (b) ZeroDivisionError in expression engine | (a) Restarted with VINU_STRATEGY_STRATEGIES_DIR, (b) ZeroDivisionError → nan guard | vinu-strategy/engine/expression.py:81 | Critical | Fixed |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
