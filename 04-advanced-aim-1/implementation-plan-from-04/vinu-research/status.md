# vinu-research — Status

**Status: implemented.** The either/or with `vinu-initial-analysis` was
decided in favor of hosting here. Full detail in [`plan.md`](plan.md).

## Files touched

**Regime recompute scan:**
- `vinu_research/scheduled/executor.py` — new `ScheduledResearchExecutor.regime_recompute_scan()`; `_run_loop()` gained a third (daily) interval alongside the existing hourly `decay_scan`/`revalidation_scan` cadence.
- `vinu_research/config.py` — new `regime_recompute_interval_days: int = 1` field + `VINU_RESEARCH_REGIME_RECOMPUTE_INTERVAL_DAYS` env override.
- `tests/test_scheduled.py` (4 tests) — disabled-when-interval-zero, posts once per deduped universe symbol with the correct URL/params, exception handling, counts only successful (200) posts.
- `tests/test_config.py` — added one assertion for the new field's default to the existing `test_research_config_defaults`.

**Research-digest generation (cross-component with `vinu-agent`'s Piece 5, `../vinu-agent/status.md`)** — found while writing `end-to-end-test/`: no run ever produced a human-readable summary, and `dispatch()` discarded `run_research()`'s return value entirely.
- `vinu_research/storage/models.py` — `ResearchRunRecord` gained `summary_text: str`.
- `vinu_research/storage/sqlite_backend.py` — schema version 3→4, migration `add_summary_text`, `insert_run`/`update_run`/`_row_to_record` updated.
- `vinu_research/llm.py` — `RUN_SUMMARY_SYSTEM_PROMPT`, `_build_run_summary_prompt()`, `ResearchLlmClient.summarize_run()` — one best-effort LLM call, gated on `is_configured()`, returns `""` on failure (matches every other method on this client).
- `vinu_research/service.py` — `run_research()` calls `summarize_run()` (gated on `config.llm_enabled`, same pattern as `refresh_strategy`'s LLM use) and persists/returns `summary_text`.
- `vinu_research/scheduled/models.py` — `ScheduledResearchJob` gained `last_run_id`/`last_summary`.
- `vinu_research/scheduled/executor.py` — `dispatch()` now captures `run_research()`'s return value and persists `last_run_id`/`last_summary` onto the job instead of discarding it.
- `tests/test_llm.py` (4 new tests) — not-configured returns empty, successful call parses `summary`, `_traced_chat` returning `None` returns empty, prompt-builder includes key metrics.
- `tests/test_sqlite_backend.py` (1 new test) — `summary_text` round-trips through `insert_run`/`update_run`.
- `tests/test_storage_models.py` — updated `test_to_dict`'s field-count assertion (20→21) for the new field.
- `tests/test_scheduled.py` (1 new test) — regression-locks the `dispatch()` fix: `job.last_run_id`/`job.last_summary` actually get set from `run_research()`'s return value.

## Bugs / Fix Log

- **`ScheduledResearchExecutor.dispatch()` discarded `run_research()`'s entire return value** — every scheduled/cron-triggered run's `report_md`/metrics were unrecoverable without separately guessing which `/research/runs` row it produced. Fixed as part of the research-digest work above; confirmed via a new regression test.

## Test run

`python3 -m pytest -q --ignore=tests/test_calibration_persistence.py --ignore=tests/test_routes.py --ignore=tests/test_routes_hypothesis.py --ignore=tests/test_routes_trade_plan.py --ignore=tests/test_trade_plan_authoring.py` (the 5 ignored files fail to collect in this environment on a clean checkout too — `ModuleNotFoundError: vinu_tools`, unrelated to this work) from `vinu-research/`: **500 passed** (was 489; +11 new tests), 1 pre-existing unrelated failure (`test_lazy_service_initialization`, tries to `mkdir('/data')` with no permission — reproduced identically on a stashed clean copy of the file), 1 skipped. `TestThreadSafety::test_concurrent_writes` is flaky (SQLite WAL lock contention under 4 threads, ~1-in-5 on this machine, reproduced independent of these changes) — not a correctness regression, not chased further.
