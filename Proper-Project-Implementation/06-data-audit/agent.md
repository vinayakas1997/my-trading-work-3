# Data audit: vinu-agent

Checked 2026-10-08 on the running stack (`agent-api`; `/data` 194 MB: 13 databases, `trade_audit.log`, `safety_ledger.jsonl`, `swarm/`, empty `memory/` and `sessions/`).

## What triggers it
- **Teams** (research team, screener team, allocator team and others) run on the planner-worker timer and on events; each team is a manager plus specialists calling tools and the local model.
- **Order path:** the agent's trade tool and order guard receive every order (from the live scheduler or from an agent decision), check it, send it to Alpaca paper, and write the audit entries.
- **Workers:** planner (picks tickers from the screener), significance triage, capital allocator, ticker summaries.

## Data items

### A1 Team runs  `team_runs.db: team_runs` (112), `team_tasks` (760)
- **Format:** run id, team, status, verdict, result JSON, LLM calls used, times. By team: research 49 (17 done, 32 failed), screener 63 (31 done, 31 failed, 1 running); all between 2026-10-06 and 2026-10-08.
- **Failed runs (63 of 112, 56%)** keep `verdict ''` and `result_json {}`: the cause is not stored with the run. It can only be found in `llm_calls`: 48 failed model calls (HTTP 502 from the upstream model server, request timeouts, connection errors), each after 3 attempts. A failed run costs about 1,300-1,560 s.
- **Consumers:** the agent's own team tools and `/agent` status routes; reflection reads `team_runs.db` for its analysts. **Verdict:** `used`, but a failed run `loses its cause` (DA-A2).

### A2 Model calls  `llm_calls.db: llm_calls` (5,977 rows, 183 MB in two days)
- **Format:** per call: team, agent, role, tier, provider, model, full prompt JSON, tools JSON, response, tokens, latency, success, error. Research specialists made 4,262 calls (51.7 million tokens), screener specialists 1,181 (8.7 million), managers 534 (3.1 million). Mean latency 14 s, longest 366 s.
- **Consumers:** the agent only (`llm.py` writes, `team.py`, `significance_triage.py`, `service.py` read), plus scripts. No pruning: about 90 MB a day. **Verdict:** `single use` and unbounded (DA-A3).

### A3 Order and agent audit  `trade_audit.log` (1,289 lines of JSON, 316 KB) and `safety_ledger.jsonl` (10 events)
- **Format (audit):** `id, action, session_id, symbol, details, metadata, paper_trading, timestamp`. Actions seen: `AuditVerdictFail` 1,264 (the claim fact-checker flagging numbers in agent text, for example "-40%" for ABBV), `order_rejected`, `order_size_scaled`, `FactRegistryWrite` 6, and the other order actions.
- **Tag defect (fixed):** every entry said `paper_trading: false` although the stack trades Alpaca paper, and no entry carried `account_mode`. Now each entry carries `account_mode` and `paper_trading` follows it (problem-log P65).
- **Safety ledger:** hash-chained halt/resume events, already tagged with the money mode (P59).
- **Consumers:** reflection (29 files read the audit log), live (4), infra; the order path writes it. **Verdict:** `used well`. 98% of it is the fact-checker's output, which buries the other 19 records (the orders) (DA-A4).

### A4 Ticker records  `ticker_ledger` (84 events), `ticker_summaries` (16), `ticker_snapshots` (17)
- **Format:** events per ticker (`triage_freshness_*` 44, `candidate_proposed` 22, `summary_refreshed` 18), an LLM-written summary per ticker, daily snapshots. **Consumers:** planner/ticker gate, reflection `screener_agreement` (reads `candidate_proposed` to test the screener). **Verdict:** `used well`.

### A5 Unified memory  `unified_memory.db: memory_entries` (0), `sync_watermarks` (0)
- A searchable memory of research, strategies, simulator runs, prices and news, filled by `SyncService`. **Nothing in the production code ever calls `SyncService`** (`sync_all`, `sync_symbol`), so the store has always been empty, and the `query_memory` tool reads an empty store. The news-reader fix of P63 is correct but has nothing to run it (DA-A1).

### A6 Small stores
`facts_registry` (6 verified facts), `daily_limits` (1), `skill_audit` (1), `significance_flags` (0), `symbol_limits` (0), `symbol_overrides` (0), `telemetry.db` (`llm_calls` 0, `steps` 0: a second, empty copy of the call log), `swarm/*.json` (96 KB). **Verdict:** limits and flags `empty` because nothing has set them; `telemetry.db` `unused duplicate` (DA-A5).

## Where the agent reaches the market
live scheduler / agent decision -> order guard (mandate, kill switch, session multiplier, free cash) -> Alpaca paper; every outcome in `trade_audit.log`.
