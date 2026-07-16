# Bugs Found: Angle 18 — Research Loop

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | `vinu_research.runner` module not importable | ImportError: No module named vinu_research.runner | Package structure differs from expected import paths | None | vinu-research | High | Open |

## Notes
- Code exists on disk at `vinu-research/vinu_research/` with files: runner.py, walk_forward.py, decay.py, scheduled/, etc.
- The module name or package exports need adjustment to match documented import paths

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
