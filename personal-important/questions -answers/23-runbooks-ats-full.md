# Runbooks ATS vs Full - When Rerun + Test Status (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `23`. Related: `04`, all runbooks.
Status: Runbooks step closed small. No code, docs + rule only.

---

## ATS 15min wiring 0-9 (smoke, fast check)

Window `VINU_STAGE1_START_DATE=2026-06-17` short 2 weeks before Q3 tier2, or `2026-03-01` 6mo safer. File `test-plan/ats-pattern/04-ats-runbook.md:1`. Tickers AAPL MSFT NVDA via seed. One at a time, stop on first fail.
Stages 0 watchlist_gate dedupe, 1 summary 27 ok but thin, 2 triage K=3, 3 idea recipe, 4 sweep 1 iter thin may hit min_trades 30 fail expected, 5 verdict, 6 risk PEND, 7 capital ACTIVE or PENDBLOCK, 8 shadow 5d thin, 9 monitor hold or exit. Cross-cut ledger ref_id + freeze + throttle 10/sec + dedupe 300s + feature cache + returns 60s. Secrets warning must NOT appear.
Time 14min without build, 24min with build. Use after any docker change, before Full. Saves time. Keep docs + scripts forever. `questions -answers/02` Q21 keep ATS.

## Full 2022 edge 0-7 (prod proof, slow)

Window `2022-01-01` full 3.5y. File `test-plan/full-pattern/03-full-runbook.md:1`. AAPL first then MSFT NVDA same table same test_run_id different ticker `UNIQUE(test_run_id,ticker,stage)` resume.
Stages 0 gate dedupe, 1 summary 27/27 1D 1125 kronos ok, 2 triage tier + rejections + recipe, 3 sweep ranked + completeness + rehearsal 7d, 4 risk APPROVED size Kelly, 5 capital ACTIVE or PENDBLOCK batch + corr, 6 shadow paper Sharpe degradation 0.5 min 5d, 7 monitor hold exit rebalance. Thresholds prod: deflated 0.95, holdout 20 percent, PBO, walk 3, stress 2020/2022, 30+ trades. After AAPL repeat MSFT NVDA. Go-live gate `05-go-live-gate.md`, edge cases `04-edge-cases.md`, preflight `02-preflight`, scope `01-scope`.
Time 30min+ sweep 1D+1H. Use for edge proof, not wiring. Needs 07-20 docs fixes to PASS, today STOP -1.06 crossover.

## When rerun rule (never lost)

- After any `docker-compose.yml`, Dockerfile, `.env-example`, secrets, entrypoint change: rerun ATS 15min first. Green -> Full 1 ticker. Red -> fix, no Full.
- After prompt, sweep, allocator, monitor code change: rerun ATS 1 ticker fast, then Full 1 ticker, then 3 tickers.
- After quarter close Q3 2026-07-01 to Q4 2026-10-01: Full re-runs new window `2022_2026-10-01` via `quarters.py`. ATS stays short window, no change.
- Env switch: ATS `VINU_STAGE1_START_DATE=2026-06-17`, Full `2022-01-01`. Flip env + restart, no rebuild. Same timers fast 60/60/90/90/90.

## Test status per run_id (ephemeral vs permanent)

- Ephemeral deletable per run_id: `test-plan/test-status/` run evidence. Delete after gate green per `inefficiencies-A-J.md:22`. Keeps folder small.
- Permanent architecture: `inefficiencies-A-J.md` ledger + `implementations/batch-*.md` source file:line dest file:line + SHA + pytest + verify. Plus `04-v2` diagram. Plus `01` to `23` docs chain here. Keep forever.
- TickerLedger rows keep for gate evidence. `SELECT * WHERE ticker=AAPL ORDER BY timestamp`. ref_id resolves via `verify_ref_id` fail-open.

## Knobs for runbooks (kept, no new)

- `VINU_STAGE1_START_DATE` ATS short vs Full 2022. `VINU_TIER2_PERIOD_MONTHS=3`. `VINU_AGENT_WATCHLIST_SEED_TICKERS=AAPL,MSFT,NVDA`. Timers fast kept. `VINU_RESEARCH_MAX_ITERATIONS=5`, `min_trades_for_pass 30`, `promotion_dsr 0.95`, `min_paper_days 5`, `degradation 0.5` kept.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives both ATS + Full symbols, no extra knob.

---

## Order (docs only, no code)

1. Keep ATS docs + scripts. Done. Rerun rule above pinned here.
2. Full needs 07-20 code fixes to PASS. Docs ready, code open. Build one by one prompt -> sweep -> top3 -> paper -> risk -> monitor -> broker.
3. Delete test-status per run_id after green. Keep ledger + 01-23 forever.

After 1-3, runbooks done. Full docs 01 to 23 closed.

---
Link: Remaining corners entrypoints first + 4 next is in `24-remaining-corners.md`. 23 -> 24 = runbooks -> corners closed. Full docs 01 to 24 closing.

---

## All covered proof (nothing missed for runbooks)

- ATS `01-scope`, `02-preflight`, `03-api-lines`, `04-ats-runbook:7-18` stages 0-9 + cross-cut covered.
- Full `01-scope`, `02-preflight`, `03-full-runbook:7-14`, `04-edge-cases`, `05-go-live-gate` covered.
- `04-v2` diagram + `04` full-progress DB plan kept. `UNIQUE(test_run_id,ticker,stage)` resume kept.
- Ledger H ref_id + freeze + throttle + dedupe + cache + returns kept.
- Thin trade_count ATS expected fail vs Full 30+ pass distinction kept. Secrets warning absent kept.
- 01-22 chain kept. 23 closes runbooks. 01 to 23 full docs closed.
