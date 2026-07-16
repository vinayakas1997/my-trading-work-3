# Bugs Found: Angle 21 — RL Training Environment

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|   |-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | SimulatorEnv init accepts `tickers`, `price_data`, `config` (not `symbols`, `initial_capital`, `cost_model`) | `unexpected keyword argument 'symbols'` | Test script used wrong kwarg names for SimulatorEnv API | Updated env creation to use `tickers`, `price_data`, `config=SimulationConfig(...)` | angle21_rl_environment.py | High | Fixed |
| 2 | SimulatorEnv.step() expects N-element weight array (no cash dimension) | Broadcast error (3,) vs (2,) | step() normalizes weights and treats cash as residual | Changed weights from 3 to 2 elements (AAPL, MSFT); cash is implicit | angle21_rl_environment.py | High | Fixed |

## Notes
- SimulatorEnv is importable via `vinu_simulator.engine.simulator.SimulatorEnv`
- The gym-compatible interface works correctly once imported

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
