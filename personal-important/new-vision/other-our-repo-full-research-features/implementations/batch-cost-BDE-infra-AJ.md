# Batch Cost B+D+E + Infra A+J — 2026-09-07

## Source → Dest

- **D (loop feature/angle cache):** `vinu-research/loop.py:141` new `_angle_context_cache` + `_feature_snapshot_cache` `LRUCache` + `loop.py:239` cache key `symbol:interval` for `get_angle_context`, `symbol` for `get_feature_snapshot` — avoids repeated `features-api:8082` + 4× `get_angle_rows` per `research_from:research_to`
- **A (double-write dedupe):** `vinu-agent/agent/scheduler_workers.py:72` `make_summary_agent_fn` now checks `ticker_summary_store.get_summary(ticker)` `updated_at` within 300s before invoking `screener` LLM team — avoids second upsert `team.py:_apply_team_result_hook` + `RunLogTrigger`
- **J (double fetch cache):** `vinu-portfolio/service.py:42` new `_returns_cache` TTL 60s + `service.py:178` `_fetch_strategy_returns` caches by `artifact_id`/`name` for both `yaml` and `llm_python` paths — `build_portfolio` + `allocate_risk_parity` no longer double fetch same `equity` series per `900s` cycle
- **E (vectorized sweep) and B (planner batch):** spiked via `03-per-repo-deep-dive/vectorbt-sweep.md` — remain backlog; `batch-cost` now covers D+A+J, B/E next

## Commits

- This commit: `feat(research,agent,portfolio): cache + dedupe for cost A+D+J`

## Tests

- `pytest vinu-research/tests/test_loop.py -q` 57 green (existing)
- `pytest vinu-portfolio/tests/test_service.py -q` 39 green
- Manual verify: `TickerSummaryStore` last-write-wins deduplicated; `features-api` called once per symbol per run

## How to verify

- Run `research` loop twice for same `AAPL` same `from/to` — second run hits cache, no second `features-api` GET
- `planner-worker` `screener` for same ticker within 5 min returns cached summary, no second LLM `screener` team run
- `portfolio` `build_portfolio` with same artifact_ids twice within 60s — second `equity` fetch served from `_returns_cache`
