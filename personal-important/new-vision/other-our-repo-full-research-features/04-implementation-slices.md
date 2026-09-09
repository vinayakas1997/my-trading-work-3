# 04 — Implementation Slices (Build Order)

> Dependency-ordered slices covering `pending-items-to-be-implemented.md` Row 1-16 plus adoptable Row 20/21/24. Do not parallelize across dependency lines. Plan-mode Product Required style: file:line + acceptance.

## Slice A1 — Foundation (1-2 days)

| Row | What | Where | Acceptance |
|---|---|---|---|
| 1 | Role d 7-day rehearsal | `vinu-research/loop.py:149` after `rank_candidates` + `sweep.py:159` → call `simulator.py:32` `WeightSimulator` with 7-day window on winner, store/summarize before `risk_gatekeeper` | `vinu-research/tests/` new test: winner → 7-day backtest exists, metrics net-of-cost, row in `TickerLedger` `stage=sweep_verdict` |
| 5 | Sizing decision | `vinu-agent/config.py:106` + `vinu-portfolio/service.py:build_portfolio` — choose Kelly vs HRP vs ATR; document in `02-reference-repos-core-logic.md` | Decision doc dated; `PyPortfolioOpt` HRP/L2 or Kelly fraction parameterized |

- **Why first:** A1 reuses existing engine (no new model), A2 is decision not code; both unblock A3.

## Slice A2 — Core replace + shock (A1-A2 must be green)

| Row | What | Where | Acceptance |
|---|---|---|---|
| 2 | Replace decision | `vinu-agent/agent/scheduler_workers.py:run_capital_allocator_cycle` + `cli.py:452` — unwind weaker `ACTIVE` if better `PEND` (via `RebalanceRequestQueue` `orchestrator.py:75`) | Test: `PEND` with higher `deflated_sharpe` triggers `rebalance_request` for weaker `ACTIVE`; Monitor keeps close authority |
| 3 | Shock trigger + batching | `vinu-live/trade_plan/orchestrator.py:100` `on_shock_event` — wire `shock_clustering/shock_personality` + batch/prioritize across open positions | Test: shock angle fires off-cycle `trade-plan-cycle`, not wait for 300s poll; prioritization covers >1 position |

## Slice A3 — Remaining custom (can interleave)

| Row | What | Where | Acceptance |
|---|---|---|---|
| 10 | TickerLedger taxonomy/retention | `vinu-agent/storage/ticker_ledger.py:19` — pin `event_type` vocab + pruning policy | Doc + test: `ref_id` resolves, retention policy dated |
| 11 | Thesis Intake skill sections | `vinu-agent/skills/thesis-intake-*/SKILL.md` + `skills/<name>/SKILL.md` `strategy-definitions`/`risk-rules` | Content landed; `skill-edit audit log` `04:104` logs edit |
| 12 | Kill Switch policy | `broker/kill_switch.py` + `rebalance_guard.check_rebalance_allowed` — decide block-even-risk-reducing? | Policy doc dated, test: halt blocks/unblocks per policy |
| 13 | env_file gap | `docker-compose.yml:9` `env_file: .env` + `secrets_loader.py:44` — remove plain-env leak or accept in writing | `docker inspect` no plain secret; `setup-secrets.sh --check` still `ready` |
| 16 | Allocator loop test | `vinu-agent/tests/test_capital_allocator_worker.py` — add scheduling loop test | Loop test covers `while True: cycle(); sleep(900)` restart |

- Rows 4 (composition), 6 (verdict debate), 7 (N/K tuning), 8 (Calibration), 9 (Triage delivery) can slot here per risk — 4/6 are med effort, 7/8/9 low.

## Slice B — Adoptable high-leverage (after A1-A3 green, before final diagram walk)

| Row | What | Where | Outer source |
|---|---|---|---|
| 20 | Risk Gateway + Throttle | `vinu-live/broker/order_guard.py` | Nautilus/Lean |
| 21 | Freeze Manifest | `vinu-infra/` + `RunLog` | Nautilus catalog / qlrk |
| 24 | Dry-run wallet | `shadow_evaluator.py:23` + `simulator/service.py` | Freqtrade dry-run |

- Acceptance for B: order rate cap 10/sec + size band, freeze hash of `data/*` inputs, wallet-level fill diff not just Sharpe.

## After all slices → Diagram walk (Phase C)

- One ticker stage-by-stage `A→1→7` + cross-cutting per `04-implementation-slices.md` earlier plan; then 2 tickers × 9 edge cases with `TickerLedger` evidence. Not before A1-A3 green — otherwise recording known fails.

## Effort ballpark

- A1: low (engine exists) · A2: low (decision) · A2-core: med · A3-custom: low-med each · B: low-med each.
