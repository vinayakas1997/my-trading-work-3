# DA-32 🟡 No Cross-Request Feature Caching

**Component:** `vinu-tools`
**Files Changed:** None

## Problem

The audit suggested that feature computation results across different requests could benefit from cross-request caching (e.g., an LRU cache of computed feature sets).

## Investigation

`vinu-tools` already has hash-based dedup at the request level via `FeatureHasher` / `JobHash`. Every incoming request generates a unique hash from the feature spec, and identical parallel requests are merged. The system is stateless by design — feature results are stored in parquet and re-read on subsequent requests (which is fast with predicate pushdown).

Adding a cross-request memory cache would:
1. Add complexity (TTL, invalidation, memory management)
2. Provide negligible benefit (re-computation from parquet is already fast)
3. Risk serving stale results if underlying data changes

## Decision

**Not needed.** Marked as `Completed (Not Needed)`. Existing hash-based dedup is sufficient.

## Verification

No code changes required. Confirm by review of `vinu-tools` code:
- `vinu_tools/compute/catalog.py` — `JobHash` dedup
- `vinu_tools/compute/registry.py` — request-level caching of alpha computations
