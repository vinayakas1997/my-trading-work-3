# Bugs Found: Angle 19 — Strategy Expressions

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | Expression `(close - BB_LOWER_20) / (BB_UPPER_20 - BB_LOWER_20)` fails with unknown variable `close` | `Unknown variable: 'close'` | Expression context dict missing `close` key | Added `'close': 100.5` to ctx | `angle19_strategy_expressions.py:24` | Low | Fixed |
| 2 | `vinu_strategy.engine.rules` module not found | `No module named 'vinu_strategy.engine.rules'` | `RuleEngine` class did not exist | Created adapter wrapping existing `RulesEngine` from `rules_engine.py` | `vinu_strategy/engine/rules.py` | Medium | Fixed |
| 3 | `vinu_strategy.loader` module not found | `No module named 'vinu_strategy.loader'` | YAML strategy loader function did not exist | Created module with `load_strategy()` wrapping `StrategyRegistry` singleton | `vinu_strategy/loader.py` | Medium | Fixed |

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
