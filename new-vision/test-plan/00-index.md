# Test Plan — Index (ATS vs Full)

> Folder: `new-vision/test-plan/` — two patterns so any agent knows how/what to test: **ATS** (minimal API-line + keys + short window) vs **Full** (full 7-stage + 2-entry + 9-edge gate). Companion to `04-new-full-explanation-v2.md` (2026-09-07 v2 diagram), `03-how-to-start.md` v2 (2026-09-07 env knobs), `pending-items-to-be-implemented.md` Status 2026-09-07, and `vinu_infra/freeze.py` lineage. Created 2026-09-07.

## Which pattern when

| Pattern | Window | Tickers | Stages | Time | Purpose |
|---|---|---|---|---|---|
| **ATS** `ats-pattern/` | `3-6mo` short `VINU_STAGE1_START_DATE=2026-03-01` (6mo) or `2026-06-01` (3mo) — must be **before** `2026-07-01` Q3 tier2 boundary or `quarters.py` tier2 reports `no_data` (`env-example:153`) | 3 (`AAPL,MSFT,NVDA` — `VINU_AGENT_WATCHLIST_SEED_TICKERS`) | `Gate` → `1 Summary` → `2 Planner` → `3 sweep+rehearsal 7d` → `4 risk` → `5 allocator+replace` → `6 Live+Shadow` → `7 Monitor` once, `TickerLedger` `ref_id` per stage | ~15 min | Plumbing proves wiring live, without waiting for `2022-01-01→now` 3.5-year backfill |
| **Full** `full-pattern/` | `2022-01-01` full (`04:16-18` origin, comparable across tickers for `RunLog` dedup `has_existing_run()` + calibration) | same 3, **each × 9 edges** | above + 9 edges×2, `composition_view` gaps, `cycle_shock_batch` prioritized, `freeze_manifest` drift, throttle `10/sec`, observed `Kill halt/resume`, observed `Triage` delivery | ~paper days + gate | Production proves no silent live loss — go-live gate `full-pattern/05-go-live-gate.md`, no partial pass |

Flow: **ATS C1** (short, 3 tickers) → **ATS C2** paper continuous (shadow twin) → flip to `2022-01-01` → **Full** (real `deflated_sharpe 0.95` + `holdout 20%` + `walk_forward 3` + `PBO` + `stress 2020/2022`).

## File map

- `requirements.md` — minimum things required: API line (9 services), keys/secrets, env (`VINU_*_DATA_ROOT`, `VINU_STAGE1_START_DATE`), watchlist — so other agents don't guess/invent.
- `ats-pattern/` — minimal pattern (scope, preflight, API lines, runbook with *what wil happen* per stage).
- `full-pattern/` — full gate (scope, preflight, stage-by-stage `trigger → response → store → TickerLedger ref_id` for one ticker, 9 edges, go-live checklist).
- `test-status/` — **ephemeral, deletable** run evidence: per `(test_run_id,ticker,stage)` `status → how fixed` for future reference; delete whole folder after gate green or per `run_id`. Also holds `timings.jsonl` (per-stage durations, via `scripts/collect-timings.py`), `timing-baselines.json` (p50/p90, `--promote`), and `failures.jsonl` (watchdog incidents, via `scripts/watchdog.py`).
- `assets/api-endpoints.csv` — 9 services port/prefix/health/protected example (copy, not invent).
- `ats-status-and-next-steps.md` — **live ATS scoreboard** (2026-09-07): how far stages 0–9 actually got, the per-service strategy-store split bug that was fixed, the LLM free-tier blocker, and exact steps to finish 6→9. Read this first to resume.

## How to use

1. Read `requirements.md` (API line + keys + watchlist).
2. For fast check: `ats-pattern/02-preflight → 03-api-lines → 04-ats-runbook` (6mo `2026-03-01`).
3. For gate: `full-pattern/02-preflight → 03-full-runbook → 04-edge-cases → 05-go-live-gate`.
4. After each test step, agent appends one line to `test-status/manifest.jsonl` + `ledger.md` with `status`, `evidence_ref` real `ref_id`, and if `fail` then `fixed_by` commit + `fixed_how`.
