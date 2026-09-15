# Full recorded information

Every place the "vinu" system persists data to disk, across all 7 packages
— not "what the service does" (that's `04-new-full-explanation-v2.md`) or
"what order it runs in" (that's `03-granularity-understanding/`), but
specifically: **what gets recorded, where it physically lives, in what
format, why it exists, and who actually reads it back** (versus stores
that are write-only dead weight today).

Built from a full-repo pass across `vinu-agent`, `vinu-research`,
`vinu-portfolio`, `vinu-live`, `vinu-screener`, `vinu-stock-price`,
`vinu-initial-analysis`, and `vinu-infra` (the shared-utility package).
Real table/file names, real column names, real function names throughout
— nothing paraphrased.

## How to read this doc

Each store gets the same 5 fields:
- **What** — one line, what the data actually is.
- **Where** — exact file path + format (SQLite table, JSONL, Parquet, plain JSON/Markdown).
- **Why** — which real decision or consumer needs this, not a generic justification.
- **Fields** — the real schema.
- **Writers / Readers** — real function and file names on both ends. If nothing reads it back in production, that's called out explicitly — it's the single most useful fact in this doc for deciding what's worth wiring up next.

Almost every SQLite store below is built on the same shared base class,
`vinu_infra.sqlite.SQLiteBackend` — thread-local connections, WAL mode,
`busy_timeout`, and a `SCHEMA` + `SCHEMA_VERSION` + `MIGRATIONS` pattern
for schema evolution. That's not repeated per store below.

## Quick reference — every store, one line each

| # | Store | Package | Format | Status |
|---|---|---|---|---|
| 1 | `ticker_ledger` | vinu-agent | SQLite | Actively consumed |
| 2 | `llm_calls` (vinu-agent) | vinu-agent | SQLite | **Write-only** |
| 3 | `ticker_summaries` | vinu-agent | SQLite | Actively consumed |
| 4 | `ticker_daily_snapshots` | vinu-agent | SQLite | **Write-only** |
| 5 | `team_runs` / `team_tasks` | vinu-agent | SQLite | Actively consumed |
| 6 | Unified memory (`memory_entries`) | vinu-agent | SQLite + FTS5 | Actively consumed |
| 7 | Facts registry (`facts`) | vinu-agent | SQLite | Actively consumed |
| 8 | `paper_performance` | vinu-agent | SQLite | Actively consumed |
| 9 | `daily_limits` | vinu-agent | SQLite | Actively consumed |
| 10 | `symbol_overrides` | vinu-agent | SQLite | Actively consumed |
| 11 | `symbol_limits` + history | vinu-agent | SQLite | Actively consumed |
| 12 | `significance_flags` | vinu-agent | SQLite | Consumed (CLI only) |
| 13 | `skill_edit_audit` | vinu-agent | SQLite | **Write-only** |
| 14 | Session/message/attempt store | vinu-agent | JSON + JSONL files | Actively consumed |
| 15 | Swarm runs | vinu-agent | JSON files | Actively consumed |
| 16 | Hash-chained safety ledger | vinu-agent | JSONL | Actively consumed (tamper audit) |
| 17 | `trade_audit.log` | vinu-agent | JSONL | Actively consumed |
| 18 | `TraceWriter` | vinu-agent | JSONL | **Dead code** (zero callers) |
| 19 | Strategy/artifact store (`artifacts` + history tables) | vinu-research | SQLite | Actively consumed |
| 20 | Judgment store | vinu-research | JSONL | **Unused in production** |
| 21 | Scheduled research jobs | vinu-research | JSON file | Actively consumed |
| 22 | Shadow account profiles | vinu-research | JSON files | **Effectively unwired** |
| 23 | Trade-score calibration history + state | vinu-research | JSONL + JSON | Actively consumed |
| 24 | Legacy `llm_cache` | vinu-research | SQLite | Superseded, kept for tests |
| 25 | Research trace writer | vinu-research | JSONL | **Write-only** |
| 26 | `llm_calls` (vinu-infra, shared client) | vinu-infra | JSONL | **Write-only** (log), cache IS read |
| 27 | `llm_cache.db` (vinu-infra, shared client) | vinu-infra | SQLite | Actively consumed |
| 28 | `telemetry.db` (`llm_calls`/`steps`) | vinu-infra | SQLite | **Write-only** |
| 29 | `trade_audit_log.jsonl` | vinu-infra (written by vinu-live) | JSONL | Actively consumed |
| 30 | `calibration_log.jsonl` | vinu-infra | JSONL | Offline-only by design |
| 31 | `ParquetStore` | vinu-infra | Parquet (utility) | Unused in these packages |
| 32 | `AllocationHistoryStore` | vinu-portfolio | SQLite | **Write-only** |
| 33 | `BookBackend` (positions/closed/fills) | vinu-live | SQLite | Actively consumed |
| 34 | `CorrelationMonitorStore` | vinu-live | SQLite | **Write-only** |
| 35 | `RebalanceRequestQueue` | vinu-live | SQLite | Actively consumed |
| 36 | LESSON JSON snapshots | vinu-live | JSON files | **Write-only** |
| 37 | `RuleStore` | vinu-screener | SQLite | Actively consumed |
| 38 | `WatchAuditStore` | vinu-screener | SQLite | Actively consumed |
| 39 | `RankerStore` | vinu-screener | SQLite | Actively consumed |
| 40 | `RankedSnapshotStore` (incl. `trace_json`) | vinu-screener | SQLite | Actively consumed |
| 41 | `RankerChurnStore` | vinu-screener | SQLite | Actively consumed |
| 42 | `symbol_catalog` | vinu-stock-price | SQLite | Actively consumed |
| 43 | `backfill_jobs` | vinu-stock-price | SQLite | Consumed (self, across runs) |
| 44 | `ingest_log` | vinu-stock-price | SQLite | **Write-only** |
| 45 | `provider_fallback_log` | vinu-stock-price | SQLite | Actively consumed |
| 46 | `backfill_runs` | vinu-stock-price | SQLite | Actively consumed |
| 47 | `vinu_settings` | vinu-stock-price | SQLite | Actively consumed |
| 48 | `watchlist_tickers` + shared JSON | vinu-stock-price | SQLite + JSON | Actively consumed |
| 49 | `events` / `events_meta` | vinu-stock-price | SQLite | Actively consumed |
| 50 | OHLCV 1m bar files | vinu-stock-price | Parquet | Actively consumed (the core dataset) |
| 51 | `runs` (RunLog) | vinu-initial-analysis | SQLite | Actively consumed |
| 52 | Angle result files | vinu-initial-analysis | Parquet | Actively consumed (the core dataset) |
| 53 | Fact sheets | vinu-initial-analysis | Markdown files | Regenerated, not read back |
| 54 | Model weights | vinu-initial-analysis | `.pt` (torch) | Actively consumed |
| 55 | `angle_run_status` | vinu-initial-analysis | SQLite | Built, but **not wired into production** |

---

# vinu-agent

### 1. Ticker Ledger — `ticker_ledger` table

- **What**: Append-only, one-row-per-event narrative log of everything that happened for a ticker across the pipeline (gate checks, triage decisions, funding, rejections). Never duplicates the real data — `ref_id` points into whichever specialized store owns the record.
- **Where**: `vinu_agent/storage/ticker_ledger.py` → SQLite table `ticker_ledger`, DB file `ticker_ledger.db` (`data_root / "ticker_ledger.db"`).
- **Why**: The shared counter/audit trail so K-cap checks, repeated-rejection detection, and significance triage don't each maintain their own drift-prone counters. Also the traceability spine behind the `/ticker_ledger` HTTP routes.
- **Fields**: `ledger_id PK, ticker, timestamp, stage, event_type, text, ref_id DEFAULT '', source DEFAULT ''`. Indexes on `ticker`, `stage`.
- **Writers**: `TickerLedgerStore.add_event()` — called from `agent/thesis_intake_gate.py`, `agent/planner_triage_hook.py`, `agent/ticker_gate.py` (`ChangeGate`/`RunLogTrigger` on lookup failures), `agent/scheduler_workers.py`, `agent/capital_allocator_hook.py`, `tools/trade_plan_tool.py` (WAIT-decision logging).
- **Readers**: `get_events()`/`count_events()` — consumed by `agent/significance_triage.py` (repeated-rejection / large-funding pattern detectors), `agent/planner_triage_hook.py` (K-cap check), `agent/thesis_intake_gate.py`, the `/ticker_ledger` HTTP route, and `cli.py`. No update/delete methods — structurally append-only.

### 2. LLM Call Log — `llm_calls` table (vinu-agent's own)

- **What**: Full prompt/response/token/latency log for every LLM call made anywhere inside vinu-agent (orchestrator, team managers, specialists).
- **Where**: `vinu_agent/storage/llm_calls.py` → table `llm_calls`, DB file `llm_calls.db`.
- **Why**: Post-hoc, call-by-call context-usage inspection.
- **Fields**: `call_id PK, created_at, service, tier, team, agent, role, session_id, provider, model, base_url, prompt_json, tools_json, response_content, response_tool_calls_json, prompt_tokens, completion_tokens, total_tokens, token_count_source, retry_count, latency_sec, success, error`. Indexes on `created_at`, `tier`, `session_id`.
- **Writers**: `LlmCallLogStore.record()` — invoked from `agent/llm.py`.
- **Readers**: **None found in production.** `get_call`/`list_calls`/`total_tokens_by_tier` exist but have no caller outside tests.

### 3. Ticker Summaries — `ticker_summaries` table

- **What**: One row per ticker holding the Summary Agent's latest angle-synthesis read (all 28 angles reduced into prose + `angle_digest` JSON) — overwritten, not versioned, per refresh. Also the persisted state the Phase-0 Change Gate compares against.
- **Where**: `vinu_agent/storage/ticker_summaries.py` → table `ticker_summaries`.
- **Why**: So downstream consumers (trade-plan authoring, forecast prompts) don't re-run angle synthesis, and so `ChangeGate` (`agent/ticker_gate.py`) can tell whether anything actually changed since the last pass.
- **Fields**: `ticker PK, summary, angles_with_data, angle_count, source_run_id, created_at, updated_at, last_checked_run_id, last_checked_artifact_signature, angle_digest (JSON)`. Schema v3.
- **Writers**: `upsert_summary()` (Summary Agent output), `record_gate_check()` (`ChangeGate.record_pass()`).
- **Readers**: `get_summary()`/`list_summaries()` — read by `ChangeGate.check()`/`RunLogTrigger.check()`, `cli.py`, and summary-display routes.

### 4. Ticker Daily Snapshots — `ticker_daily_snapshots` table

- **What**: Dated, per-day-per-ticker point-in-time snapshot of the angle digest/summary — the only queryable "what was true about ticker X on day Y" store (the ledger is event-only; `ticker_summaries` only holds "latest").
- **Where**: `vinu_agent/storage/ticker_snapshots.py` → table `ticker_daily_snapshots`, PK `(ticker, snapshot_date)`.
- **Why**: Raw material for a future narrating agent / Hindsight `retain` pipeline that needs "yesterday's state" — built this session, foundation work ahead of that agent.
- **Fields**: `ticker, snapshot_date, summary, angle_digest (JSON), angles_with_data, angle_count, source_run_id, created_at`.
- **Writers**: `record_daily_snapshot()` — called from `agent/ticker_gate.py`'s `RunLogTrigger` (optional `ticker_snapshot_store` DI param).
- **Readers**: `get_snapshot`, `get_latest_before`, `list_snapshots` exist, but **no production reader today** — write-only until the narrating agent exists.

### 5. Team Runs / Team Tasks — `team_runs`, `team_tasks` tables

- **What**: Orchestrator run tracking — which LLM team ran, its status/verdict, budget used, and the individual agent tasks within a run.
- **Where**: `vinu_agent/storage/team_runs.py` → tables `team_runs`, `team_tasks`.
- **Why**: "Every run that touched artifact X" / "every run session S triggered" traceability.
- **Fields** — `team_runs`: `run_id PK, team_name, triggered_by_session_id, status, verdict, result_json, llm_calls_used, time_used_seconds, error_message, created_at, updated_at, completed_at, related_artifact_id`. `team_tasks`: `task_id PK, run_id, agent_name, role, depends_on (JSON), status, result, error, started_at, completed_at`.
- **Writers**: `create_run`, `mark_running/done/failed/cancelled`, `add_task`, `mark_task_*`, `set_related_artifact_id`.
- **Readers**: `get_run`, `list_runs`, `list_tasks`, `list_by_artifact_id`, `list_by_session_id` — used by `server/routes_trace.py` (cross-referenced with `trade_audit.log` and the research strategy store) and status surfaces.

### 6. Unified Memory Store — `memory_entries`, `sync_watermarks` + FTS5

- **What**: Cross-source searchable memory (notes/facts from research, simulator, stock-price, agent, news), with a composite recency/source-weight/FTS-rank scoring function.
- **Where**: `vinu_agent/memory/unified_store.py` → `memory_entries`, `sync_watermarks`, virtual table `memory_fts` (FTS5).
- **Why**: One searchable "what do we know about symbol X" instead of separate per-source lookups; `sync_watermarks` lets each source's ingester resume where it left off.
- **Fields** — `memory_entries`: `id PK, source, source_id, symbol, memory_type, title, content, summary, metadata (JSON), score, created_at, updated_at`. `sync_watermarks`: `source PK, last_sync_at, last_id`.
- **Writers**: `add_entry`, `bulk_add`, `delete_entry(s)`, `set_watermark`.
- **Readers**: `scored_search`/`search`/`list_by_symbol`/`recent_entries` — used by `service.py` for memory-backed context retrieval.

### 7. Facts & Limitations Registry — `facts` table

- **What**: Permanent, provable facts / disproven approaches / known bugs (e.g. "direction prediction from sentiment doesn't work"), so future runs don't rediscover a disproven approach.
- **Where**: `vinu_agent/facts/registry.py` → table `facts`.
- **Fields**: `id PK, statement, kind (proven|disproven|known-bug), symbols (JSON), signals (JSON), evidence_ref, status (active|superseded), established_date, created_at, updated_at`.
- **Writers**: `add_fact()` (also mirrored into `AuditLogger.log(FACT_REGISTRY_WRITE, ...)`), `supersede()`.
- **Readers**: `active_facts_for(symbols, signals)`, `count_active()` — injected into agent context/prompts by `service.py`.

### 8. Paper Performance Store — `paper_performance` table

- **What**: Per-artifact daily paper-trading returns — persisted so Shadow's `min_paper_days≥5` gate accumulates across restarts (previously an in-memory dict that reset every restart).
- **Where**: `vinu_agent/broker/performance_store.py` → table `paper_performance`, `VINU_AGENT_DATA_ROOT/paper_performance.db`.
- **Fields**: `artifact_id PK, returns_json (JSON list[float]), updated_at REAL, meta_json (JSON)`.
- **Writers**: `record_daily_return`/`record_daily_returns`/`record_meta` — via `server/routes_broker.py` HTTP endpoints (external callers, e.g. vinu-live, POST daily returns).
- **Readers**: `get_daily_returns`/`get_all`/`get_meta` — used by `routes_broker.py` and the Shadow promotion gate's `min_paper_days` check.

### 9. Daily Order Limits — `daily_limits` table

- **What**: Real, persistent, cross-process per-symbol daily order-count/volume counters for `OrderGuard`'s `max_daily_orders`/`max_daily_trade_volume` mandate check. Fixes a bug where a fresh in-memory dict per `OrderGuard()` construction made the cap non-functional.
- **Where**: `vinu_agent/broker/daily_limits.py` → table `daily_limits`, `VINU_AGENT_DATA_ROOT/daily_limits.db`.
- **Fields**: `symbol, date, order_count, volume`, PK `(symbol, date)`.
- **Writers**: `record_order()` — called from `OrderGuard.pre_approve()`, atomic `UPSERT` with retry/backoff (a real 30-thread race was found and fixed here).
- **Readers**: `count_today`, `count_today_total` (portfolio-wide daily cap), `volume_today` — read by `OrderGuard` on every order.

### 10. Symbol Overrides — `symbol_overrides` table

- **What**: Operator-set per-symbol override state (`untradeable` / `reduce_only` / `ignored`) that beats any mandate check.
- **Where**: `vinu_agent/broker/symbol_overrides.py` → table `symbol_overrides`, `VINU_AGENT_DATA_ROOT/symbol_overrides.db`.
- **Fields**: `symbol PK, state, reason, set_by, set_at REAL`.
- **Writers/Readers**: `set()`/`get()`/`all()`/`clear()` — consulted by `OrderGuard` before every order.

### 11. Symbol Limits + History — `symbol_limits`, `symbol_limit_history` tables

- **What**: Per-symbol overrides of mandate-level numeric limits (`max_order_value`, `max_position_pct`, `max_capital_utilization_pct`), plus a full change history answering "why is AAPL capped at $500?".
- **Where**: `vinu_agent/broker/symbol_limits.py` → `symbol_limits` (current state), `symbol_limit_history` (append-only), `VINU_AGENT_DATA_ROOT/symbol_limits.db`.
- **Fields** — `symbol_limits`: `symbol PK, max_order_value, max_position_pct, max_capital_utilization_pct, reason, set_by, set_at`. `symbol_limit_history`: `id PK AUTOINCREMENT, symbol, field, old_value, new_value, reason, set_by, changed_at`.
- **Writers/Readers**: `set()`/`clear_field()`/`clear()` write both tables; `get()`/`all()`/`history()` read — consulted by `OrderGuard` (limits) and reporting surfaces (history).

### 12. Significance Flags — `significance_flags` table

- **What**: Flags raised by Significance Triage (repeated-rejection, large-funding, thesis-contradiction patterns) surfaced to a human via Discord/Telegram — never blocks anything.
- **Where**: `vinu_agent/agent/significance_triage.py` → table `significance_flags`.
- **Fields**: `flag_id PK, ticker, reason, detail, created_at, responded_at, response_text, resolved, muted_until, skill_version`.
- **Writers**: `create_flag()`, `mute_flag()`, `mark_responded()` — driven by the pattern detectors, which query `ticker_ledger` directly (no separate counter).
- **Readers**: `get_flag`, `response_rate()` (alert-fatigue measurement, now logged once per significance-worker cycle — see `cli.py`) — no dedicated HTTP route besides CLI.

### 13. Skill Edit Audit — `skill_edit_audit` table

- **What**: Content-hash-based change log of whether a risk-relevant skill file (`thesis-intake-risk-rules/SKILL.md`) changed and when — visibility, not access control.
- **Where**: `vinu_agent/agent/skill_audit.py` → table `skill_edit_audit`, `skill_audit.db`.
- **Fields**: `entry_id PK, skill_path, detected_at, old_hash, new_hash, old_line_count, new_line_count, diff_summary`.
- **Writers**: `check_skill_edits()`/`SkillAuditStore.record()` — run by `cli.py`'s `skill_audit_worker_main` (default 3600s).
- **Readers**: `get_latest()`/`get_history()` exist but have **no production caller** outside the worker's own diffing logic.

### 14. Session / Message / Attempt Store — files, not SQLite

- **What**: Per-session chat/agent-run state: session metadata, message transcript, per-attempt (agent run) records including the ReAct trace.
- **Where**: `vinu_agent/session/store.py`, one directory per session:
  - `<session_id>/session.json` (atomic write, tmp+`os.replace`)
  - `<session_id>/messages.jsonl` (append-only, `fsync`'d)
  - `<session_id>/attempts/<attempt_id>/attempt.json`
- **Why**: The durable record behind vinu-agent's chat/session API.
- **Fields** — `Session`: `session_id, title, status, created_at, updated_at, last_attempt_id, config`. `Message`: `message_id, session_id, role, content, created_at, linked_attempt_id, metadata`. `Attempt`: `attempt_id, session_id, parent_attempt_id, status, prompt, run_dir, summary, react_trace, error, metrics, created_at, started_at, completed_at`.
- **Writers/Readers**: `create_session/update_session/append_message/save_attempt` write; `get_session/list_sessions/get_messages/get_attempt` read — used by `session/service.py`, `service.py`, `agent/scheduler_workers.py`.

### 15. Swarm Runs — JSON files

- **What**: Debate/investment-committee "swarm" run state (status, final report, per-run vars) — one JSON file per run.
- **Where**: `vinu_agent/swarm/store.py` → `<base_dir>/<run_id>.json`, atomic write.
- **Why**: `find_latest_run()` lets trade-plan authoring opportunistically fold a completed `investment_committee` debate into the signal ledger.
- **Writers/Readers**: `save()`/`update_status()` write; `get()`/`list()`/`find_latest_run()` read — consumed by `server/routes_swarm.py`'s `/swarm/runs/latest` and trade-plan authoring.

### 16. Hash-Chained Safety Ledger — `safety_ledger.jsonl`

- **What**: Tamper-evident, `fsync`'d, hash-chained append-only log of the highest-stakes safety events (kill-switch halt/resume, emergency flatten). Each entry's hash chains from the previous one, so any edit/reorder/delete breaks `verify()` from that point forward.
- **Where**: `vinu_agent/broker/audit_ledger.py` (`HashChainedLedger`) → `VINU_AGENT_AUDIT_LEDGER` (default `VINU_AGENT_DATA_ROOT/safety_ledger.jsonl`).
- **Fields** (one JSON object per line): `seq, ts, event_type, payload, prev_hash, hash`.
- **Writers**: `HashChainedLedger.append()` — kill-switch/emergency-flatten events.
- **Readers**: `entries()`, `verify()` (walks the whole chain, reports the first broken link) — after-the-fact tamper audits.

### 17. Trade/Order Audit Log — `trade_audit.log` (JSONL)

- **What**: Structured audit trail of every trading/agent-governor action (risk checks, order placed/filled/rejected, kill-switch/mandate/fact-registry writes, journal entries).
- **Where**: `vinu_agent/broker/kill_switch.py` (`AuditLogger`) → `VINU_AGENT_AUDIT_LOG` (default `VINU_AGENT_DATA_ROOT/trade_audit.log`).
- **Fields**: `{id, action, session_id, symbol, details, metadata, paper_trading, timestamp}`. Action constants: `RiskCheckPassed/RiskCheckFailed/OrderPlaced/OrderFilled/order_rejected/order_pending_confirmation/order_executing/order_error/GroundTruthInjected/AuditVerdictFail/AuditVerdictStale/RuntimeSettingChanged/JournalEntryCreated/JournalStatusChanged/FactRegistryWrite`.
- **Writers**: `AuditLogger.log()` — called from `tools/trade_tool.py` (every order path), `tools/trade_plan_tool.py`, `broker/debrief.py`, `audit/fact_audit.py`, `audit/ground_truth.py`, `facts/registry.py`, `server/app.py`, `server/routes_broker.py`. Fail-open (never raises).
- **Readers**: `AuditLogger.search(ref_id)` — used by `server/routes_trace.py` to join order/session/artifact ids across `trade_audit.log`, `team_runs.db`, and the research strategy store.

### 18. React Trace Writer — dead code

- **What/Where**: `vinu_agent/agent/trace.py` (`TraceWriter`) — per-session step-by-step JSONL trace writer.
- **Status**: **Fully dead code** — no caller anywhere in vinu-agent outside its own file. `Attempt.react_trace` (item 14) is populated some other way.

---

# vinu-research

### 19. Strategy / Artifact Store — `artifacts` + history tables

- **What**: The central research artifact (trade-strategy) store — lifecycle status (`CREATED→BENCHING→PEND/PENDBLOCK→ACTIVE→MONITORING→DECAYED/DISABLED`), backtest metrics, generated code, trade-plan data, plus append-only bench/decay/calibration history.
- **Where**: `vinu_research/storage/strategy_store.py` (`SqliteStrategyStore` — a hand-rolled backend, not `SQLiteBackend`). Tables: `artifacts`, `bench_history`, `decay_snapshots`, `calibration_entries`, `angle_calibration_entries`, `proposed_decay_actions`.
- **Why**: The authoritative record of every strategy artifact's identity, status, and validation history — read by risk_gatekeeper, capital_allocator, Shadow/vinu-live promotion, the Summary Agent (per-angle trust via `get_angle_calibration`), and vinu-agent's `team_runs.related_artifact_id`/`ticker_ledger.ref_id`.
- **Fields (`artifacts`)**: `artifact_id PK, type, name, universe (JSON), status, decay_horizon, signal_definition, entry_rules, exit_rules, created_at, updated_at, strategy_code, source_run_id, initial_sharpe, initial_max_dd, deflated_sharpe, holdout_passed, stress_test_passed, pbo, last_validated_ts, revalidation_count, last_revalidation_verdict, trade_plan_data, approved_size, origin_angles (JSON), regime_tag, freeze_hash, timeframe`.
  - `bench_history`: `id PK, artifact_id FK, date, ic, ir, ic_positive, sharpe`.
  - `decay_snapshots`: `id PK, artifact_id FK, evaluation, ic_ratio, rolling_ir, ic_positive_ratio, rolling_sharpe, n_entries, timestamp`.
  - `calibration_entries` / `angle_calibration_entries`: `id PK, [angle_name,] artifact_id FK, forecast_direction, actual_return_pct, forecast_magnitude_pct, brier_score, directional_correct, magnitude_error, timestamp`.
  - `proposed_decay_actions`: `artifact_id PK FK, from_status, proposed_status, created_at`.
- **Writers**: `upsert_artifact`, `transition_status`/`mark_*`, `append_bench_entry`, `append_calibration_entry`, `append_angle_calibration_entry`, `save_snapshot`, `record_proposed_decay_action` — driven by the research pipeline, `risk_gatekeeper_hook.py`, `trade_plan_authoring.py::record_realized_outcome`, `ScheduledResearchExecutor.decay_scan()`.
- **Readers**: `get_artifact`, `list_artifacts(_for_symbol/_by_statuses)`, `list_stale_artifacts`, `get_bench_history`, `get_calibration_entries`, `get_angle_calibration_entries` (→ the Summary Agent's per-angle trust signal), `get_latest_snapshot`/`get_snapshots`, `get_proposed_decay_action` — read by vinu-agent's `ChangeGate`, `verify_ref_id`, decay-approval flow, Shadow's promotion gate. **The `reasoning` field inside `trade_plan_data`'s embedded forecast is now also surfaced at the top level of the `GET/POST /trade-plan/{id}` API response** (routes_trade_plan.py's `_artifact_to_dict`) — previously computed and stored but never read back anywhere.

### 20. Judgment Store — JSONL

- **What**: Per-iteration research verdict log (in-sample/out-of-sample/holdout Sharpe, verdict, verdict correctness, LLM calls used).
- **Where**: `vinu_research/judgment_store.py` (`JudgmentStore`) — caller-supplied path, no default.
- **Status**: **Unused in production** — never instantiated anywhere in `vinu_research/` outside its own module and tests.

### 21. Scheduled Research Jobs — `jobs.json`

- **What**: Persisted scheduled research job definitions (cadence, status, last-run info), one JSON file holding all jobs.
- **Where**: `vinu_research/scheduled/store.py` → `~/.vinu/scheduled_research/jobs.json` (atomic write).
- **Writers**: `save()`, `delete()`, `recover_stale_running()` (crash recovery: resets `RUNNING`→`PENDING` on restart).
- **Readers**: `get()`, `list_all()`, `count()` — used by `cli.py` and `scheduled/executor.py`.

### 22. Shadow Account Profiles — JSON files

- **What**: One JSON file per "shadow" broker-account profile (reconstructed trading history/journal used to seed Shadow evaluation), keyed by content hash.
- **Where**: `vinu_research/shadow/storage.py` → `~/.vinu/shadow_accounts/<shadow_id>.json`.
- **Status**: **Effectively unwired** — only referenced by its own module/tests; `shadow/extractor.py` only reuses the static `compute_hash()` helper. No live route or executor calls `save()`/`load()`.

### 23. Trade-Score Calibration History + State

- **What**: The self-calibrating `TradeScoreThresholds` machinery — history of each closed trade's 4 sub-scores joined to realized return, plus a state file holding currently-active thresholds and any pending proposal.
- **Where**: `vinu_research/trade_score_calibration.py`. History: `VINU_TRADE_SCORE_CALIBRATION_HISTORY` (default `VINU_RESEARCH_DATA_ROOT/trade_score_calibration_history.jsonl`). State: `VINU_TRADE_SCORE_CALIBRATION_STATE` (default `.../trade_score_calibration.json`).
- **Why**: Fits/nudges `TradeScoreThresholds`' 4 sub-max weights toward whatever historically predicted winning trades, bounded step size, gated by a minimum sample and (in propose mode) human approval.
- **Fields (history)**: `timestamp, direction, actual_return_pct, tier, total_score, confluence_score, ev_score, risk_score, regime_fit_score`. **Fields (state)**: `{"active": {...}, "active_metadata": {...}, "proposal": {"thresholds": {...}, "metrics": {...}, "proposed_at": ...}}`.
- **Writers**: `record_trade_score_outcome()` (from `trade_plan_authoring.py::record_realized_outcome`), `save_proposal()`/`apply_directly()` (from `ScheduledResearchExecutor`), `approve_proposal()`.
- **Readers**: `read_history()`, `compute_calibration_metrics()`, **`load_active_thresholds()`** — the live path: every trade-plan scoring call and the approval-recheck gate load the currently active thresholds from here (this is also the store behind the trade_score_gate divergence bug fixed this session — approval used to check against a fresh default-thresholds object instead of this file's active state).

### 24. Legacy Research LLM Cache — `llm_cache` table

- **What/Where**: `vinu_research/llm.py` (`LlmCache`) — caller-supplied path, table `llm_cache`.
- **Status**: Superseded by vinu-infra's shared `LlmCache` (item 27) — kept only for test backward-compatibility, not the live path for `ResearchLlmClient`.

### 25. Research Trace Writer — `traces/<run_id>.jsonl`

- **What**: Per-research-run JSONL log of every LLM call (`chat_json`, `diagnose_failure`, `suggest_pivot`, `validate_idea`, `characterize_stock`, `summarize_run`) with 200-char-truncated prompt/response previews and latency.
- **Where**: `vinu_research/llm.py` (`ResearchTraceWriter`) → `data_root / "traces" / f"{run_id}.jsonl"`.
- **Status**: **Write-only** — no code in `vinu_research/` reads the `traces/` directory back; a duplicate of the fuller vinu-infra `llm_calls.jsonl` log, truncated to 200 chars.

---

# vinu-infra (shared utilities)

### 26–27. Shared LLM Client Triad — `llm_calls.jsonl`, `llm_cache.db`, `telemetry.db`

The base `LlmClient`/`AsyncLlmClient` (used by both vinu-agent's `agent/llm.py` and vinu-research's `ResearchLlmClient`) writes three parallel sinks per call:

- **`llm_calls.jsonl`** (`vinu_infra/llm/client.py::_log_llm_call()`): full `system_prompt`/`user_prompt`/`response`/`duration_sec`/`success`/`error`/`token_usage`/`estimated_cost_usd` per call. Path: `data_root / "llm_calls.jsonl"`. **Write-only** — no in-package reader, forensic/manual-inspection log only.
- **`llm_cache.db`** (`vinu_infra/llm/cache.py::LlmCache`, table `llm_cache`: `cache_key PK, response_json, created_at`) — TTL'd cache keyed by a hash of the prompt. **Actively consumed** — `LlmCache.get()` is checked on every call, a real cache-hit path.
- **`telemetry.db`** (`llm_calls`, `steps` tables, `vinu_infra/telemetry.py`) — see item 28.

### 28. Telemetry Store — `telemetry.db` (`llm_calls`, `steps`)

- **What**: A second, queryable sink for LLM-call and non-LLM pipeline-step/tool-call telemetry (token usage, retries, latency, outcome codes) — additive to `llm_calls.jsonl`.
- **Where**: `vinu_infra/telemetry.py` → tables `llm_calls`, `steps`; path caller-supplied (`data_root / "telemetry.db"`).
- **Fields** — `llm_calls`: `id PK, ts, service, model, base_url, prompt_tokens, completion_tokens, total_tokens, token_count_source, retry_count, latency_sec, success, outcome, error`. `steps`: `id PK, ts, service, step_name, duration_sec, success, outcome, data_volume_in, data_volume_out, error`.
- **Writers**: `record_llm_call_safe()`/`record_step_safe()` (best-effort) — called from vinu-agent's `agent/loop.py` and vinu-infra's `llm/client.py`/`client_async.py` on every chat call.
- **Readers**: `recent_llm_calls()`, `recent_steps()`, `summary()` exist but have **no production caller** anywhere — built to close a real observability gap (a 22-day replay incident where nothing measured this live) but nothing queries it back yet.

### 29. Trade Audit Log — `trade_audit_log.jsonl`

- **What**: Append-only, best-effort JOIN-KEY log of per-trade lifecycle events (`entry`/`exit`), keyed by `trade_id` (the position book's `position_id`), joining entry-time decision context to exit-time outcome.
- **Where**: `vinu_infra/trade_audit_log.py` → `VINU_TRADE_AUDIT_LOG` (default `VINU_DATA_ROOT/trade_audit_log.jsonl`). Written primarily by vinu-live's `orchestrator.py`.
- **Fields**: common envelope `{trade_id, symbol, event, timestamp}`; `entry` context: `artifact_id, direction, entry_decision, trade_score_tier, trade_score_total, trade_score_reasons, risk_band, fill_price, fill_qty, intended_qty, partial_fill, slippage_bps, slippage_exceeded`; `exit` context: `artifact_id, exit_action, exit_rule, realized_pnl, qty, avg_entry, loss_cause`.
- **Writers**: `record_entry()`/`record_exit()` — vinu-live's orchestrator (`_maybe_enter` fill path, `_record_trade_exit`).
- **Readers**: `read_by_trade_id()` — orchestrator's own loss classifier and `feedback_loop.py`'s upstream-push enrichment; `read_all()`/**`slippage_stats()`** (new: a TCA rollup — mean/median/max slippage_bps, exceeded count, optional symbol filter) — exposed via vinu-live's `GET /live/tca/slippage` route (previously the raw slippage number was computed and thrown away past the pass/fail `slippage_exceeded` boolean).

### 30. Calibration Log — `calibration_log.jsonl`

- **What**: Append-only observation log for reasoning-picked (not measured) threshold decisions (rebalance-protect gain threshold, bracket take-fraction, thesis-duplicate similarity cutoff).
- **Where**: `vinu_infra/calibration_log.py` → `VINU_CALIBRATION_LOG` (default `VINU_DATA_ROOT/calibration_log.jsonl`). Only records when a real broker (paper or live) is connected.
- **Fields**: `{checkpoint, timestamp, ...context}` — free-form per checkpoint.
- **Writers**: `record(checkpoint, context)` — best-effort, from vinu-agent/vinu-live call sites.
- **Readers**: `read_all(checkpoint=None)` — **explicitly offline-only by design**, never on a live decision path.

### 31. ParquetStore — generic utility

- **What**: A reusable Parquet append/dedup/consolidate utility (PyArrow-backed).
- **Where**: `vinu_infra/parquet.py`.
- **Status**: **Unused within vinu-agent/research/infra** — the real parquet writers for time-series data live in `vinu-stock-price`/`vinu-initial-analysis` (their own hand-rolled parquet code, items 50/52 below), which don't use this shared class.

---

# vinu-portfolio

### 32. Allocation History — `allocation_history` table

- **What**: One row per calendar day of the portfolio's computed target allocation — weights, sleeve splits, equity/reserve figures. A dated snapshot of `compute_daily_allocation()`'s output, previously computed fresh every call and thrown away.
- **Where**: `vinu_portfolio/storage/allocation_history.py` → `<data_root>/allocation_history.db`, table `allocation_history`, PK `allocation_date`.
- **Why**: Nothing else in vinu-portfolio carries allocation state across restarts (`self._last_weights` is in-memory only). Built this session as foundation for a future narrating agent's "what did the portfolio look like yesterday" question.
- **Fields**: `allocation_date PK, weights (JSON), sleeves (JSON), interval_sleeves (JSON), account_equity, reserve_fraction, reserve_amount, deployable_equity, created_at`. Each entry in `weights` also now carries a `vol_annualized` field per strategy (the intermediate volatility estimate behind risk-parity weighting, previously computed then discarded once the weight was produced).
- **Writers**: `record_daily_allocation()` — called from `service.py::compute_daily_allocation` (best-effort, idempotent per-day upsert).
- **Readers**: `get_allocation`/`get_latest_before`/`list_allocations` exist but **no production caller yet** — same "built ahead of the narrator" status as items 4 and 34.

---

# vinu-live

### 33. Position Book — `open_positions`, `closed_positions`, `fills` tables

- **What**: The live position book — ground truth for what's open, what closed (with realized P&L), and every fill that produced those positions.
- **Where**: `vinu_live/book/positions.py` → `<data_root>/trade_plan_book.db`.
- **Why**: Drives daily-loss-limit checks, position lifecycle, reconciliation, the feedback loop, and (read-only) the lesson worker's trade-count gate.
- **Fields** — `open_positions`: `position_id PK, symbol, side, qty, avg_entry, realized_pnl, stop_loss, take_profit, opened_at, updated_at, partial_taken, artifact_id`. `closed_positions`: same shape plus `closed_at, close_price, feedback_processed_at`. `fills`: `fill_id PK, symbol, side, qty, price, filled_at, position_id, commission`.
- **Writers**: `open_position`, `add_to_position`, `reduce_position`, `close_position`, `update_stop_loss`, `mark_feedback_processed` — from `orchestrator.py` (entries/exits) and `feedback_loop.py`.
- **Readers**: `get_position`, `list_open_positions` (every cycle, plus `breaker/engine.py`), `daily_realized_pnl` (daily-loss limit), `list_closed_positions(unprocessed_only=True)` (feedback loop's push-upstream), and `lesson_worker.py`'s raw read-only count for the 30-trade lesson trigger.

### 34. Correlation Monitor History — `correlation_monitor_history` table

- **What**: Per-cycle history of the runtime pairwise-correlation check output (which pairs flagged, which reduces taken) — previously recomputed every cycle and discarded after being returned once.
- **Where**: `vinu_live/trade_plan/correlation_monitor_store.py` → `<data_root>/correlation_monitor.db`.
- **Why**: Built this session so a pair's correlation climbing over days, or a flag skipped due to cooldown, is actually auditable — foundation for the narrating agent.
- **Fields**: `id PK AUTOINCREMENT, checked_at, n_flagged, flagged (JSON), reductions (JSON)`.
- **Writers**: `record_cycle()` — from `orchestrator.py`'s runtime-correlation check, once per cycle where the check actually ran.
- **Readers**: `list_recent()` exists but **no production caller yet**.

### 35. Rebalance Request Queue — `rebalance_requests` table

- **What**: One-pending-request-per-symbol queue of capital-allocator-initiated rebalance requests (advisory only, never a direct action).
- **Where**: `vinu_live/trade_plan/rebalance_intake.py` → `<data_root>/rebalance_requests.db`.
- **Why**: Must be SQLite-backed (not in-memory) because the HTTP intake route constructs a *fresh* `TradePlanOrchestrator` per request — a different object from the long-running worker's orchestrator that evaluates requests each cycle.
- **Fields**: `symbol PK, reason, requested_at, critical` (a critical request bypasses the 5%-unrealized-gain protect rule).
- **Writers**: `submit()` — from `TradePlanOrchestrator.submit_rebalance_request()`, itself called by `POST /trade-plan/rebalance-request`.
- **Readers**: `pending_for(symbol)` — read every cycle by the long-running orchestrator; `consume(symbol)` deletes the row once evaluated.

### 36. LESSON JSON Snapshots

- **What**: Periodic "lesson" summary snapshots — closed-trade count, fill count, avg commission, last-5 win/loss streak, HALT state — written once a rolling closed-trade threshold is crossed.
- **Where**: `vinu_live/lesson_worker.py::write_lesson()` → `<data_root>/lessons/LESSON_<timestamp>.json` (or `STAR_LESSON_<timestamp>.json` for high-evidence lessons, ≥50 closed trades).
- **Fields**: `closed, fills, avg_commission, last5 (e.g. "WWLWL"), halted, at`.
- **Writers**: `cycle() → write_lesson()`, on a worker interval (default 3600s).
- **Readers**: **None found in-scope** — presumably consumed by an external, out-of-scope review/narration tool.

---

# vinu-screener

### 37. Rule Store — `rules` table

- **What**: Persisted CRUD + enable/disable state for `ScanRule` condition-based watch rules.
- **Where**: `vinu_screener/rules/store.py` → `<DEFAULT_DATA_ROOT>/screener_rules.db`.
- **Fields**: `rule_id PK, rule_json (JSON: condition/universe/cooldown_min/coarse_filter/actions/mode), interval_sec, active, created_at, updated_at`.
- **Writers**: `upsert_rule()`, `delete()`, `set_active()` — from operator HTTP routes and the scheduler's own one-shot self-deactivation.
- **Readers**: `all(active_only=True)` — read every scheduler tick, drives which rules run.

### 38. Watch Audit Store — `fired_watches` table

- **What**: Permanent, append-only record of every rule "fire" event — distinct from the live, transient cooldown/arming state.
- **Where**: `vinu_screener/audit/watch_history.py` → `<DEFAULT_DATA_ROOT>/screener_audit.db`.
- **Fields**: `id PK AUTOINCREMENT, rule_id, symbol, fired_at, detail`. Indexes on `(rule_id, fired_at)` and `(symbol, fired_at)`.
- **Writers**: `record_many()` — from `scheduler.py::_handle_result()` whenever a rule fires.
- **Readers**: `history()` — exposed at `GET /screener/rules/{rule_id}/history`.

### 39. Ranker Store — `rankers` table

- **What**: Persisted CRUD + enable/disable state for factor-based `RankerConfig` definitions (the ranker equivalent of item 37).
- **Where**: `vinu_screener/rankers/store.py` → `<DEFAULT_DATA_ROOT>/screener_rankers.db`.
- **Fields**: `ranker_id PK, ranker_json, interval_sec, active, created_at, updated_at`.
- **Writers/Readers**: CRUD via `/screener/rankers*` HTTP routes; `all(active_only=True)` read every tick by `RankerScheduler.tick()`.

### 40. Ranked Snapshot Store — `ranker_snapshots` table

- **What**: The single latest ranked result per ranker (top-N candidates + per-filter-stage pipeline trace) — a durable cheap-read cache.
- **Where**: `vinu_screener/rankers/snapshot_store.py` → `<DEFAULT_DATA_ROOT>/screener_ranker_snapshots.db`.
- **Fields**: `ranker_id PK, generated_at, top_json (JSON list of {symbol, factor_score, risk_penalty, concentration_penalty, final_score, risk_flags, fields}), trace_json (JSON list of per-filter-stage before/after counts — added this session, previously computed by ScreenPipeline.run() and dropped before reaching storage or the API response)`.
- **Writers**: `set_latest()` — from `churn.py::record_ranking()`, the single shared path both the scheduler and the on-demand rank route use.
- **Readers**: `get_latest()` — `GET /screener/rankers/{ranker_id}/latest` (now includes `trace`) and internally for churn diffing.

### 41. Ranker Churn Store — `ranker_churn_events` table

- **What**: Permanent, queryable history of rank churn — which symbols entered/exited a ranker's top-N between two consecutive rankings.
- **Where**: `vinu_screener/rankers/churn.py` → `<DEFAULT_DATA_ROOT>/screener_ranker_churn.db`.
- **Fields**: `id PK AUTOINCREMENT, ranker_id, symbol, kind ("entered"|"exited"), at, from_rank, to_rank`.
- **Writers**: `record()` — from `churn.py::record_ranking()`, whenever `diff_rankings()` produces events.
- **Readers**: `history()` — `GET /screener/rankers/{ranker_id}/churn`.

---

# vinu-stock-price

### 42. Symbol Catalog — `symbol_catalog` table

- **What**: Per-symbol ingest bookkeeping — provider, first/last bar timestamp, archive coverage, live file, backfill completeness, adjustment/gap status.
- **Where**: `vinu_stock/catalog/store.py` → `<data_root>/vinu_stock_price.db`, table `symbol_catalog`.
- **Why**: The backfill orchestrator and live ingest cycle need a durable watermark (`last_bar_ts`) to resume without re-fetching from providers.
- **Fields**: `symbol PK, provider, first_bar_ts, last_bar_ts, archive_through, live_file, backfill_status, updated_at, has_adj_data, gap_count, last_validation_at`.
- **Writers**: `upsert_symbol`/`update_bar_range` — from `backfill/orchestrator.py`, `live/ingest_cycle.py`.
- **Readers**: `backfill/orchestrator.py` (resume point), `live/ingest_cycle.py` (per-symbol watermark), `GET /catalog[/{symbol}]`.

### 43. Backfill Jobs — `backfill_jobs` table

- **What**: One row per (symbol, year) historical-backfill unit, with status/row count/error.
- **Where**: Same DB, table `backfill_jobs`.
- **Why**: Resumable/idempotent backfill — a year already `done` is skipped next run.
- **Fields**: `id PK, symbol, year, status ('queued'/'running'/'done'/'failed'), provider, rows_written, error, updated_at`, `UNIQUE(symbol, year)`.
- **Writers/Readers**: `queue_backfill_job`/`set_job_status`/`get_job_status` from `backfill/orchestrator.py::_backfill_symbol`.

### 44. Ingest Log — `ingest_log` table

- **What**: Append-only audit of every ingest attempt (backfill year job or live poll) per symbol.
- **Where**: Same DB, table `ingest_log`.
- **Status**: **Write-only** — `log_ingest()` called from `backfill/year_job.py` and `live/ingest_cycle.py`; no `SELECT` anywhere in the codebase reads it back.
- **Fields**: `id PK, symbol, run_at, bars_added, from_ts, to_ts, ok, error`.

### 45. Provider Fallback Log — `provider_fallback_log` table

- **What**: Record of every time a provider chain fell through to a non-primary provider, including which earlier providers failed and why.
- **Where**: Same DB, table `provider_fallback_log`. Built this session.
- **Why**: This was computed inside `fetch_bars_with_fallback` and discarded once a later provider succeeded — no way to see how often or why failover happens.
- **Fields**: `id PK, symbol, role, winning_provider, skipped_errors (JSON), occurred_at`.
- **Writers**: `record_fallback()` — from `providers/registry.py::_record_fallback_if_any`, only when a prior provider in the chain actually failed first.
- **Readers**: `list_recent_fallbacks()` → `GET /catalog/fallbacks[?symbol=]`.

### 46. Backfill Runs — `backfill_runs` table

- **What**: One row per top-level `run_backfill()` call — aggregate summary (symbols attempted, years ok/failed, total rows, rows rolled, errors).
- **Where**: Same DB, table `backfill_runs`. Built this session.
- **Why**: The run-level rollup used to only exist in a printed report or one HTTP response body, lost once the process exited.
- **Fields**: `id PK, run_at, symbols (JSON), years_attempted, years_ok, years_failed, total_rows, symbols_skipped, rows_rolled, errors (JSON)`.
- **Writers**: `record_backfill_run()` — from `backfill/orchestrator.py::run_backfill`.
- **Readers**: `list_recent_backfill_runs()` → `GET /backfill/runs`.

### 47. Settings — `vinu_settings` table

- **What**: Runtime-tunable settings (poll interval, default provider, data root) as a key/value table.
- **Where**: Same DB, table `vinu_settings`.
- **Writers**: `patch()` — `PATCH .../settings`. **Readers**: `get_all()` — `GET .../settings`, plus startup defaults.
- **Fields**: `key PK, value`.

### 48. Watchlist — `watchlist_tickers` table + shared JSON file

- **What**: The set of tickers actively tracked for live ingest/backfill, plus a plain JSON file (`{"tickers": [...], "updated_at": ...}`) used to sync the watchlist with a sibling system.
- **Where**: Table `watchlist_tickers` in `vinu_stock_price.db`; shared file at env path `VINU_SHARED_WATCHLIST_PATH`, atomic write + `FileLock`.
- **Fields**: `ticker PK, added_at`.
- **Writers**: `add_tickers`/`remove_ticker` — `POST/DELETE .../watchlist`; `write_shared()` fires after every local mutation.
- **Readers**: `list_tickers()` → drives `run_live_cycle`'s default symbol set; `read_shared()` → `sync_watchlist_from_shared` merges the shared file back in.

### 49. Event-Risk Calendar — `events` + `events_meta` tables (`vinu_events.db`)

- **What**: Upcoming earnings/macro-economic events per symbol (`events`), plus per-`kind` last-pull timestamp for throttling (`events_meta`).
- **Where**: `vinu_stock/events/store.py` → separate DB file `<data_root>/vinu_events.db`.
- **Why**: `GET .../events/{symbol}` serves an upcoming-event window so trading logic can avoid holding through earnings/macro releases.
- **Fields** — `events`: `symbol, kind ('earnings'|'economic'), event_ts, title, severity (1|2), pulled_at`, PK `(symbol, kind, event_ts, title)`. `events_meta`: `key PK, value`.
- **Writers**: `replace_kind()` (full delete-then-insert snapshot per pull, not upsert) + `set_last_pull()` — from `events/poller.py::refresh_calendar`, run each live-ingest cycle.
- **Readers**: `upcoming()` → `GET .../events/{symbol}`.

### 50. OHLCV 1-Minute Bar Files — Parquet (the core price dataset)

- **What**: The actual price data — 1-minute OHLCV bars per symbol/provider, with adjustment factor.
- **Where**: `<data_root>/prices/1m/{SYMBOL}/archive/{year}.parquet` (immutable, closed years) and `.../live/{year}.parquet` + daily shards `{year}_{YYYYMMDD}.parquet` (current accumulating year). Path helpers in `storage/paths.py`, read/write in `storage/parquet.py`.
- **Fields**: `symbol, provider, bar_ts, open, high, low, close, volume, vwap, trades, adj_factor`.
- **Writers**: `write_bars` (merge+dedupe rewrite — archive years/rollover), `append_bars` (cheap daily-shard append — live ingest), `consolidate_live_shards` (merges accumulated shards once threshold exceeded). All atomic (tmp file + `os.replace`, avoiding a real truncated-file corruption bug).
- **Readers**: `query/engine.py::fetch_candles` (via DuckDB `read_parquet` glob over archive+live, in-process cached, invalidated on file signature change) — this is what `GET /candles` serves. Corrupt/unreadable files are now logged via the standard logger (not just `warnings.warn`) since this session.

---

# vinu-initial-analysis

### 51. RunLog — `runs` table

- **What**: Permanent audit of every completed/failed angle analysis run — the single source of truth for "what is the current run for symbol+angle+granularity+tier."
- **Where**: `vinu_initial_analysis/storage/meta.py` → `<data_root>/vinu_initial_analysis_runs.db`, table `runs`.
- **Why**: `AngleStorage._resolve_latest_path` resolves "the latest run" through this table rather than scanning parquet mtimes, because mtime "survives copies/backfills/clock skew badly" and had already caused a real double-counting bug.
- **Fields**: `id PK, symbol, angle_name, run_id UNIQUE, started_at, analysis_from, analysis_until, stored_at, status, error, row_count, granularity, tier, duration_seconds`.
- **Writers**: `record_run()` — from `runner.py` (bars-driven `AngleRunner`), `storage/orchestration_registry.py` (batch path), **and, since this session, `pnl_attribution_ingest.py::ingest_closed_positions`** (previously the only `AngleStorage` writer that bypassed RunLog entirely — the pnl_attribution data was readable but "when was this last updated / did it error" was invisible to every RunLog-driven consumer).
- **Readers**: `AngleStorage._resolve_latest_path`, `storage/factsheet.py::generate_factsheet`, `server/routes_v1.py::latest_run`/`fetch_by_run`, `storage/admin.py::delete_angle`.

### 52. Angle Result Files — Parquet (the core analysis dataset)

- **What**: The actual per-angle analysis/backtest output rows (one file per run) for each symbol/angle/granularity/tier — 29 angles registered in `ANGLE_REGISTRY` (Chronos forecasts, trend-lifecycle signals, GARCH volatility, shock_personality, pnl_attribution, etc).
- **Where**: `<data_root>/analysis/{symbol}/{angle_name}/{granularity}/{tier}/{run_id}.parquet` (single-ticker angles); `.../analysis/_multi/{ticker_hash}/...` (reserved, currently unused, multi-ticker path). `tier2` = scheduled/quarterly, immutable, never pruned; `tier3` = ad-hoc, pruned to `cleanup_max_runs` (default 10) oldest-first.
- **Fields**: angle-specific columns plus fixed columns: `symbol, angle_name, time_format, run_id, started_at, analysis_from, analysis_until, stored_at`.
- **Writers**: `AngleStorage.write` — from `runner.py`, `orchestration_registry.py`, `pnl_attribution_ingest.py`.
- **Readers**: `AngleStorage.read`/`read_latest` — `server/routes_read.py::get_angle` (`GET /angle/{angle_name}/{ticker}`), `server/routes_v1.py::fetch`/`fetch_by_run`, `storage/factsheet.py::generate_factsheet`.

### 53. Fact Sheets — Markdown files

- **What**: Deterministic, no-LLM Markdown summaries — one per symbol+angle, plus a combined `_summary.md` per symbol.
- **Where**: `<data_root>/factsheets/{symbol}/{angle_name}.md` and `.../_summary.md` (overwritten each time).
- **Status**: Explicitly "a readable projection, not a source of truth" — regenerated on every batch write, but `server/routes_v1.py::factsheet` calls `generate_factsheet()` directly rather than reading the persisted `.md` file, so the file on disk is a side artifact nothing reads back.

### 54. Model Weights — `.pt` files (torch)

- **What**: Serialized PyTorch weights from walk-forward training steps, for the transformer/deep-learning angles (arima, dlinear, itransformer, lpatchtst, lstm, patchtst, tft, tips_regime_aware_transformer).
- **Where**: `vinu_initial_analysis/storage/weights.py` → `<data_root>/weights/{symbol}/{angle_name}/{timeframe}/{YYYY}/{YYYYMM}/{bar_ts}.pt`.
- **Why**: Lets these angles warm-start/inference from a prior walk-forward step instead of retraining from scratch; `save()` returns a `weights_ref` stored inline in that angle's own result row.
- **Writers**: `WeightsStore.save` — from each of those 7 angles' own `backtest.py`.
- **Readers**: `WeightsStore.load` — same angles, keyed by the `weights_ref` in their stored result row. Also swept (deleted, not read) by `storage/admin.py::delete_angle`.

### 55. Angle Run Status — `angle_run_status` table

- **What**: An ephemeral, in-flight live-status board for a batch of (symbol, angle) jobs — separate from RunLog's permanent completed-run history. Rows are deleted once every job in a batch reaches `'ok'`.
- **Where**: `vinu_initial_analysis/storage/orchestration.py` → table `angle_run_status`, caller-supplied DB path.
- **Fields**: `id PK, batch_id, symbol, angle_name, status, attempts, max_attempts, last_error, started_at, heartbeat_at`, `UNIQUE(batch_id, symbol, angle_name)`.
- **Status**: **Built, fully functional, but not wired into production** — `register_batch`/`mark_running`/`heartbeat`/`mark_ok`/`mark_failed`/`stale_running_rows` all work and are exercised by `orchestration_registry.py`, but no production caller in `runner.py`, `service.py`, `api.py`, or `server/routes_*.py` actually instantiates this store — only `orchestration_registry.py` itself and tests do.

---

## What this doc makes visible at a glance

Roughly a third of the ~35 cataloged stores are **write-only today** — real
data gets computed and persisted, but nothing reads it back yet. Most of
these fall into one of two buckets:

1. **Built ahead of a consumer that doesn't exist yet** — `ticker_daily_snapshots`,
   `AllocationHistoryStore`, `CorrelationMonitorStore` were all built this
   session specifically as foundation for a future narrating/self-evaluating
   agent (see `missing-pieces-of-system/narating-agents/`). They're
   deliberately write-only until that agent exists to read them.
2. **Genuinely orphaned** — `llm_calls.db` (vinu-agent), `telemetry.db`
   (vinu-infra), `skill_edit_audit`, `ingest_log`, the research
   `traces/<run_id>.jsonl` writer, `JudgmentStore`, `ShadowStorage`, and
   `agent/trace.py`'s `TraceWriter` (fully dead code) were built for a
   real reason at the time but have no live reader today. Worth a look
   before adding anything new in the same area — the infrastructure may
   already exist.
