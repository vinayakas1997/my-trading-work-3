---
name: real-gaps-batch-implement-test
status: built -- 5 of the 7 "still unbuilt" gaps are closed; 1 was found to be already solved elsewhere; 1 is genuinely not buildable without a named provider
purpose: record of what was actually touched and tested. Not a new phase -- a direct build-out of the "Real gaps, still unbuilt" list from the prior session summary, done in one continuous pass.
---

# Real-gaps batch -- implementation record

Built 2026-08-11, directly following the kill-switch race fix in the same session.

## Item-by-item disposition

1. **News/stock-price provider pluggability** -- NOT a gap. Research
   found `vinu-news`/`vinu-stock-price` already have their own
   `@runtime_checkable Protocol` + registry (`TickerNewsProvider`/
   `TickerNewsRegistry`, `PriceProvider`/`ProviderRegistry`) with real
   multiple providers (Alpaca/Yahoo/FMP; Alpaca/Polygon/Yahoo/YFinance/
   Tushare) and fallback chains -- more built out than the broker
   abstraction. `vinu_agent`/`vinu_live` just talk HTTP to those
   services; nothing to build. Corrected the record rather than
   rebuilding something that exists.

2. **Significance Triage patterns 2 & 3** -- built. `detect_large_
   funding_pattern` (threshold sourced from `TradingMandate.max_order_value`,
   never a second invented number) and `detect_thesis_contradiction_pattern`
   (reads a new `stage="debrief", event_type="thesis_contradicted"`
   TickerLedger event, now written by `broker/debrief.py` whenever a
   close's conclusion is "contradicts"). `min_count=1` for the
   contradiction pattern -- no basis for a repeated-count threshold like
   the original pattern has.

3. **Watchlist bootstrap gap** -- built. `VINU_AGENT_WATCHLIST_SEED_TICKERS`
   (static, operator-provided) + `scheduler_workers.discover_new_tickers`/
   `bootstrap_new_tickers`, wired into `planner-worker`'s cycle: any seed
   ticker not yet in `TickerSummaryStore` gets one screener-team run to
   cold-start its first row. Deliberately not an invented market-data
   discovery integration.

4. **capital_allocator's rebalancer role** -- built. New
   `list_active_artifacts_for_rebalance` tool (real calibration data per
   ACTIVE artifact, no synthetic "weakness" score). Manager's final
   answer gets an optional `"unwind"` list, applied by
   `capital_allocator_hook.py`'s new `_request_unwind` (gated by
   `rebalance_guard.check_rebalance_allowed`, POSTs to a new vinu-live
   route). **Found and fixed along the way**: `RebalanceRequestQueue` was
   a plain in-memory dict -- the HTTP route and the real trade-plan-worker
   cron loop each construct their own `TradePlanOrchestrator`, so an
   HTTP-submitted request would have been silently invisible to the real
   cycle. Converted to a SQLite-backed store at a shared `config.data_root`
   path (same fix shape as the kill-switch lock: an in-memory/per-instance
   mechanism where the real requirement was durable, cross-process state).

5. **Per-angle calibration tracker** -- built. `Artifact.origin_angles`
   (new field, populated only from the research team's own
   `angles_used` JSON field -- real tool-call data, never inferred
   after the fact). `AngleCalibrationEntry`/`AngleCalibrationResult` +
   `angle_calibration_entries` table. `record_realized_outcome` fans the
   SAME scored outcome out to one entry per origin angle. Deliberately
   no pass/fail gate (unlike the trade-plan-level `CalibrationGate`) --
   no established null-thresholds for per-angle scoring exist; inventing
   some would be exactly the kind of ungrounded number this project
   avoids. New `GET /research/angle-calibration/{angle_name}` route.

6. **Kill-switch lock coverage / OrderGuard's other gates** -- evaluated
   as scoped. **Found a different, more serious bug in the process**:
   `OrderGuard`'s daily order-count/volume tracking was a plain
   in-process dict, but `trade_tool.py` constructs a fresh `OrderGuard`
   on every single call -- `max_daily_orders`/`max_daily_trade_volume`
   could never actually trigger, no matter how many real orders had
   already gone through that day. Not a narrow race window, a completely
   non-functioning check, with zero prior test coverage. Fixed with a new
   `DailyLimitStore` (SQLite-backed, same shape as every other
   cross-call counter in this codebase). No cross-process lock added
   here (unlike the kill switch) -- this is a soft rate limit, and the
   remaining three gates (active-artifact, market-hours, portfolio-
   concentration) are all deliberately fail-open/advisory by the
   mandate's own design, not safety-critical the way the kill switch is;
   adding lock machinery there would be disproportionate, not thorough.

7. **Second real broker provider** -- not built. No provider was ever
   named. The extension point (`broker/factory.py`'s `_PROVIDERS`
   registry) has existed since the earlier broker-abstraction work; a
   second entry is a one-line registry addition once a real provider is
   named. Building a fake one now would be exactly the kind of invented
   scope this project's discipline refuses.

## Files touched

| Repo | File | Status | What changed |
|---|---|---|---|
| vinu-agent | `vinu_agent/agent/significance_triage.py` | modified | `detect_large_funding_pattern`, `detect_thesis_contradiction_pattern`, `TickerLedgerReader` protocol |
| vinu-agent | `vinu_agent/broker/debrief.py` | modified | `ticker_ledger_store` param; writes `thesis_contradicted` event on a contradicting close |
| vinu-agent | `vinu_agent/session/service.py` | modified | passes `ticker_ledger_store` into `PositionCloseDetector` |
| vinu-agent | `vinu_agent/agent/scheduler_workers.py` | modified | `_run_detector_for_ticker` helper, all 3 patterns run per cycle; `discover_new_tickers`/`bootstrap_new_tickers` |
| vinu-agent | `vinu_agent/cli.py` | modified | `significance_worker_main` sources `funding_threshold` from the mandate; `planner_worker_main` runs bootstrap each cycle |
| vinu-agent | `vinu_agent/config.py` | modified | `watchlist_seed_tickers` (from `VINU_AGENT_WATCHLIST_SEED_TICKERS`) |
| vinu-agent | `vinu_agent/tools/rebalance_context_tool.py` | new | `ListActiveArtifactsForRebalanceTool` |
| vinu-agent | `vinu_agent/agent/capital_allocator_hook.py` | modified | `_request_unwind`, `unwind` list parsing, `services_config` param |
| vinu-agent | `vinu_agent/agent/team.py` | modified | `TeamManager(services_config=...)`, threaded to `_apply_team_result_hook` |
| vinu-agent | `vinu_agent/tools/submit_thesis_tool.py`, `delegate_tool.py` | modified | pass `services_config` into `TeamManager` |
| vinu-agent | `vinu_agent/broker/daily_limits.py` | new | `DailyLimitStore` |
| vinu-agent | `vinu_agent/broker/order_guard.py` | modified | daily counters now backed by `DailyLimitStore`, not a dict |
| vinu-agent | `teams/capital_allocator/*`, `teams/research/manager_prompt.md` | modified | unwind instructions; `angles_used` JSON field |
| vinu-agent | `vinu_agent/agent/research_artifact_writer.py` | modified | parses `angles_used` into `Artifact.origin_angles` |
| vinu-agent | `.env-example` | modified | `VINU_AGENT_WATCHLIST_SEED_TICKERS` documented |
| vinu-agent | 9 test files | new/modified | see below |
| vinu-live | `vinu_live/trade_plan/rebalance_intake.py` | rewritten | SQLite-backed `RebalanceRequestQueue` |
| vinu-live | `vinu_live/trade_plan/orchestrator.py` | modified | shared on-disk queue path; `rebalance_queue` DI param |
| vinu-live | `vinu_live/server/app.py` | modified | `POST /live/trade-plan/rebalance-request` |
| vinu-live | `tests/test_rebalance_intake.py`, `tests/test_trade_plan_orchestrator.py`, `tests/test_app.py` (new) | modified/new | |
| vinu-research | `vinu_research/models.py` | modified | `Artifact.origin_angles`; `AngleCalibrationEntry`/`AngleCalibrationResult` |
| vinu-research | `vinu_research/storage/strategy_store.py` | modified | `origin_angles` column + migration; `angle_calibration_entries` table + methods |
| vinu-research | `vinu_research/forecast_skill.py` | modified | `compute_angle_calibration` |
| vinu-research | `vinu_research/calibration.py` | modified | `get_angle_calibration` |
| vinu-research | `vinu_research/trade_plan_authoring.py` | modified | `record_realized_outcome` fans out to angle entries |
| vinu-research | `vinu_research/server/routes_trade_plan.py` | modified | `GET /research/angle-calibration/{angle_name}` |
| vinu-research | 5 test files | modified | |

## Test results

```
vinu-agent:    659 -> 716 passed (full suite; no regressions)
vinu-research: 592 -> 610 passed, 1 skipped (full suite; no regressions)
vinu-live:     149 -> 152 passed (full suite; no regressions)
```

## Known follow-ups (not blocking, not silently dropped)

- **`angles_used` is prospective only.** Every artifact created before
  this change (and any research pass that doesn't populate the field)
  has `origin_angles == []` -- no per-angle calibration data for it,
  forever. There is no way to retroactively reconstruct which angles
  informed an already-written artifact.
- **`AngleCalibrationResult` has no pass/fail gate.** It's an
  observability signal until real usage establishes what "good" looks
  like per angle -- see item 5 above.
- **The rebalancer's "weaker calibration" judgment is entirely the
  manager LLM's call**, grounded in real tool data but not independently
  re-verified by a deterministic check the way funding amounts are
  capped by `approved_size`. No `ArtifactStatus` value represents
  "flagged for unwind" -- an unwound-but-not-yet-closed artifact stays
  ACTIVE in `strategy_store` until vinu-live's own cycle actually acts.
- **`DailyLimitStore` has no cross-process lock.** A genuine (very
  unlikely) simultaneous-instant race between two orders for the same
  symbol could undercount by one. Deliberately left unlocked -- soft
  rate limit, not safety-critical; flagged, not silently accepted as
  "fine" without saying so.
- **Second broker provider and news/price-provider selection inside
  vinu_agent**: still nothing to build until a real second provider is
  named, or a nested-provider-selection need (as opposed to the
  service-level pluggability that already exists) is actually stated.
