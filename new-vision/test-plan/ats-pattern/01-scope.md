# ATS Pattern — Scope (Minimal, Not Gate)

> **Covers:** plumbing proves wiring live — does every stage execute, log to `TickerLedger`, and hand off what next stage expects? **Not:** metrics correctness, deflated Sharpe significance, or production window comparability.

## What ATS checks

- `watchlist_gate` → `summary_agent` (`TickerSummaryStore` `angles_with_data`/`angle_count` + `source_run_id` today's `RunLog` `run_id`)
- `planner_triage` + `planner_idea` (recipe + search space tied to angle, `HypothesisRegistry` consulted, K-cap shared)
- `sweep_execute` → `sweep_verdict` (ranked table + `completeness` + `PaperRehearsalResult` 7d, PASS/FAIL)
- `risk_gatekeeper` (via `get_portfolio`, sizing `fractional_kelly 0.25` `position_sizing.py:52`) → `PEND` (not `mark_active`)
- `capital_allocator` batched (`900s`) + `replace` unwind REQUEST + `composition_view` gaps + `PENDBLOCK` vs `ACTIVE` per `kill_switch`
- `live_shadow` (`ShadowEvaluator` Sharpe) + `monitor` (`TradePlanOrchestrator` hold, `cycle_shock_batch` optional)
- Cross-cutting `TickerLedger` one row per stage, `ref_id` resolves, `kill_switch` gate, `throttle 10/sec` (`order_guard.py`), `freeze_manifest` hashes

## What ATS does NOT check

- Deflected Sharpe threshold `0.95` significance (needs full `2022→now` history)
- Staged rollout canary/SPRT, tick wallet fill reconciliation (B24 still spiked)
- Observed Triage delivery (manual gate, needs creds)

## When to use

- Before Full — 3 tickers, short window `2026-03-01` (6mo), ~15 min. If ATS fails, Full will fail same reason, just slower.
