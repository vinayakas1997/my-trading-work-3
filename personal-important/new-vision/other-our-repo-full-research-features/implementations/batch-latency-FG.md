# Batch Latency F+G — 2026-09-07

## Source → Dest

- **F (allocator retry window):** `vinu-agent/tools/allocation_tool.py:116` `httpx.post timeout 30` single fail-closed → `for attempt in 2: timeout 30 then 10 + sleep 1s` retry before `funding skipped` + `LOG warning attempt 1 retrying`. Prevents one `portfolio-api:8090` hiccup stalling entire `PEND` batch until next `900s` cycle (`f7e25081` cadence).
- **G (auto shock batch wiring):** `vinu-live/trade_plan/orchestrator.py:135` `cycle_shock_batch(5)` already built `d4c338ea` (scores `shock_clustering` + `shock_personality`, sorts descending, debounced 60s). Now auto-wired in `cycle()` `orchestrator.py:218` — before `for plan in plans` loop, fetches `corr` + `pers` per symbol, builds `shock_scores`, if any `>0.5` sorts `plans` descending, logs prioritized order. Explicit `cycle_shock_batch` caller still works via debounce.

## Commits

- This commit: `feat(latency): allocator retry + auto shock batch prioritization`

## Tests

- `pytest vinu-live/tests/test_trade_plan_orchestrator.py -q` 29 green (existing)
- `pytest vinu-agent/tests/test_capital_allocator_worker.py -q` 5 green
- Manual: `portfolio-api` down 1s then up → second attempt succeeds, no batch stall; `cycle()` with one symbol `shock 0.9` prioritized first

## How to verify

- Kill `portfolio-api` for 1s during `900s` cadence → log shows `attempt 1 retrying` then success on attempt 2, not `funding_skipped_unreachable`
- Open position with high `shock_personality 0.8` vs low `0.1` — `cycle()` log shows `Shock batch prioritized order: [HIGH=0.80, LOW=0.10]` and HIGH evaluated first same cycle
- Explicit `await orchestrator.cycle_shock_batch(max_batch=5)` still respects per-symbol `60s` debounce
