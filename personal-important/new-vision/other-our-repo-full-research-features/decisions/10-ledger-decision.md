# Decision — Row 10 TickerLedger retention/taxonomy (pinned 2026-09-07)

> `04:412` `ticker_ledger.py:19`.

## Taxonomy (v1)

- `stage`: `watchlist_gate | thesis_intake | summary_agent | planner_triage | planner_idea | sweep_execute | sweep_verdict | risk_gatekeeper | capital_allocator | live_shadow | monitor | kill_switch_gate | significance_triage`
- `event_type`: `changed | unchanged | summary_refreshed | triage | proposal | sweep_complete | verdict_PASS | verdict_FAIL | APPROVED | REJECTED | PEND | PENDBLOCK | funded | rebalance_requested | rebalance_blocked | hold | decay | close_out | halt | resume | flag_created`
- `source`: `watchlist | human | human_override | system`
- `ref_id`: points to real row (`artifact_id`, `run_id`, `flag_id`)

## Retention

- Append-only, no auto-prune until 1M rows or 90 days; prune only with dated export. Mirrors `TickerSummaryStore`/`SqliteStrategyStore` durability.

## Dated

- 2026-09-07 — v1 pinned.
