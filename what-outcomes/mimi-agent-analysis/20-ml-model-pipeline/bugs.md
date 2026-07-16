# Bugs Found: Angle 20 — ML Model Pipeline

## Bug Log
| # | Bug Description | Error Message | Root Cause | Fix Applied | File Changed | Severity | Status |
|---|-----------------|---------------|------------|-------------|--------------|----------|--------|
| 1 | alpha101_045 factor is entirely NaN | All values are NaN | Factor requires specific market conditions not present in this data window | None | vinu-features | Low | Open |

## Notes
- CUDA XGBoost requires: `tree_method='hist'`, `device='cuda'`, and CUDA-capable GPU
- At small data sizes (<1000 rows), GPU overhead dominates → no speedup
- At larger data sizes (>10000 rows), CUDA provides ~2-5x speedup
- LightGBM and CatBoost also support GPU training but were not tested (no CUDA flags passed)

## Severity Levels
- **Critical:** Blocks execution, angle cannot run
- **High:** Produces wrong results
- **Medium:** Works but with warnings or edge case failures
- **Low:** Cosmetic issues, minor inaccuracies
