# Track B: Overfitting/Robustness

## What Changed

### 1. `vinu-research/vinu_research/storage/sqlite_backend.py`

**Schema changes**: `research_catalog` table extended with 4 new columns:
- `total_validated_count INTEGER NOT NULL DEFAULT 0` — number of times a strategy for this symbol survived OOS validation
- `last_validation_verdict INTEGER` — 1 = last validation passed, 0 = failed, NULL = never validated
- `consecutive_validation_failures INTEGER NOT NULL DEFAULT 0` — how many times in a row validation has failed
- `exhausted INTEGER NOT NULL DEFAULT 0` — 1 = symbol is exhausted, future research should skip it

**Migration (v2→v3)**: Added 4 ALTER TABLE statements to `_MIGRATIONS` for existing databases.

**`update_catalog_after_run` updated**: Now reads the existing catalog entry, computes the new `total_validated_count`, `last_validation_verdict`, and `consecutive_validation_failures` based on the `validated` parameter. When `consecutive_validation_failures >= 5`, the symbol is automatically marked as `exhausted`.

**`is_symbol_exhausted(symbol)`**: Returns True if:
- The catalog entry has `exhausted=1`, OR
- `lifetime_trial_count >= 20` AND `best_sharpe_ever < 0.3`

**`exhaust_symbol(symbol)`**: Manually mark a symbol as exhausted.

**`clear_exhaustion(symbol)`**: Reset exhaustion and consecutive failures counter.

### 2. `vinu-research/vinu_research/loop.py`

**Exhaustion check in `run()`**: At the start of `StrategyResearchLoop.run()`, before any iterations begin, calls `self._storage.is_symbol_exhausted(symbol)`. If True, returns early with a `ResearchResult` containing an explanatory report and zero iterations.

### 3. `vinu-research/vinu_research/service.py`

**`validated` flag**: `update_catalog_after_run` now receives `validated=True` when `holdout.passed` or `stress_test.passed` is True (was previously always `False`).

**Post-run exhaustion warning**: After the catalog is updated, checks `is_symbol_exhausted(symbol)` and logs a warning if the symbol is now exhausted.
