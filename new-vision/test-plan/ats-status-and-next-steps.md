# ATS Pattern — Status & What's Left (2026-09-07)

> One-page handoff for the `ats-pattern/` run. Records exactly how far the
> 9-stage ATS lifecycle got, what was **fixed** this session, the **hard
> blockers**, the **real gaps discovered**, and the precise steps to finish
> stages 6→9. Companion to `ats-pattern/04-ats-runbook.md` (the stage table)
> and `test-status/ledger.md` (per-run evidence). **Not** a runbook — a
> "here's where the hands-on test actually stands" memo.

## TL;DR — stage scoreboard

| Stage | Runbook name | State | Why |
|---|---|---|---|
| 0 | `watchlist_gate` | ✅ green | both runs (ledger `..._6mo`, `..._6mo_r2`) |
| 1 | `summary_agent` | ✅ green | 27/28 angles with data (post internal-Bearer fix) |
| 2 | `planner_triage` | ✅ AAPL, MSFT · ⬜ NVDA not logged | |
| 3 | `planner_idea` | ✅ green | |
| 4 | `sweep_execute` | ✅ green | real backtests, cost-aware |
| 5 | `sweep_verdict` | ⚠️ ran, **verdict FAIL** | thin 6mo data → `min_trades_for_pass 30` miss; **expected** per runbook `04:22`, not a bug |
| 6 | `risk_gatekeeper` | ✅ **proven via real hook** (manual) | `art_6862176a8ac7` BENCHING→PEND, `approved_size=6142.86` — but **no auto-trigger exists** (see Gaps) |
| 7 | `capital_allocator` | ⛔ **blocked — LLM quota** | real worker fires every 90s & sees the PEND, but its team call `404/429` (see Blockers) |
| 8 | `live_shadow` | ⬜ not run yet | 0-LLM; finishable today once an ACTIVE/BENCHING artifact exists |
| 9 | `monitor` | ⬜ not run yet | 0-LLM eval loop; finishable today |

**Bottom line:** stages 0–6 are proven; **6→7 works end-to-end but is blocked only by the OpenRouter free-tier daily cap + a pulled model slug** — not by plumbing. The big **plumbing bug this session actually found and fixed** is below.

---

## 🔧 FIXED this session (the important one)

### Strategy store was split per-service → stage 7 `ACTIVE` invisible to stages 8–9

Every service mounts its **own** host dir at `/data`, so `strategy_store.db`
was **four different files**:

- agent `data/agent/strategy_store.db` (stages 1→7 write here, in-process via
  `broker/research_link.get_strategy_store()`)
- research-api `data/research/strategy_store.db` (**serves** `/research/artifacts`)
- portfolio `data/portfolio/…`, live `data/live/…`

`ShadowEvaluator` (stage 8) + `TradePlanOrchestrator` (stage 9) reach the
store **over research-api HTTP**, so they read `data/research` — a different
DB than the agent's `data/agent`. A stage-7 `ACTIVE` therefore **never
appeared** to stage 8/9. `research_artifact_writer.py`'s own docstring
("OrderGuard reads vinu-research's real strategy_store.db") **assumes one
shared file** — the split broke that assumption.

**Empirical proof (pre-fix):** seeded BENCHING via agent writer →
`agent in-process = ['art_1d1cf2583c45']`, `research HTTP BENCHING = []`.

**Fix applied** — `docker-compose.yml`, `environment: VINU_RESEARCH_DATA_ROOT: /research-data`
+ `./data/research:/research-data` bind added to **agent-api, research-api,
portfolio-api** (live-api unchanged — it uses research-api HTTP). Agent's own
memory/ledger stay on `/data` (= `data/agent`); only the research/strategy
root is unified.

**Empirical proof (post-fix):** agent-written `art_d3fc66e9aaa8` →
`research in-process = ['art_d3fc66e9aaa8']`, `research HTTP = ['art_d3fc66e9aaa8']`. ✅

> ⚠️ **Durability caveat (TODO, not done):** one SQLite file now shared by 3
> containers over a Windows bind mount + WAL is the known "move to Postgres"
> debt (`pending-items` Row). Fine for single-artifact ATS tests; NOT proven
> safe for concurrent multi-service writes at production scale. Durable fix =
> research-api **HTTP-owns** artifacts (agent calls it instead of in-process),
> or Postgres. Decide before Full pattern.

---

## ⛔ BLOCKERS (external, not code)

1. **`minimax/minimax-m3:free` was pulled by OpenRouter** → `404: This model
   is unavailable for free … use slug minimax/minimax-m3` (paid). `VINU_LLM_MODEL`
   in `.env:31` still points at the dead `:free` slug.
2. **Free-tier daily request cap exhausted** → valid `:free` slugs return
   `429: Rate limit exceeded: free-models-per-day. Add 10 credits to unlock
   1000 free model requests`.

Consequence: stage 7's `capital_allocator` **team** can't run (`llm_calls_used=0`,
run status `failed`). The **worker itself is healthy** — it cycled on the 90s
cadence and correctly read the shared PEND. Stages 8/9 need **no LLM**, so they
are finishable today.

**To unblock stage 7:** pick ONE —
- add $10 credits to the OpenRouter key (`secrets/vinu_llm_api_key`) → unlocks 1000/day, then set `VINU_LLM_MODEL` to a working slug; or
- wait for the free daily cap to reset + repoint `VINU_LLM_MODEL` to a live `:free` slug (probe availability via `GET /api/v1/models` filtered `:free`); or
- drive stage 7 via its **real hook** `apply_capital_allocator_decision` (0 LLM) — see "finish now" steps.

---

## 🔎 REAL GAPS discovered (fix these so the pipeline is genuinely wired)

- **G1 — Stage 6 (`risk_gatekeeper`) has NO trigger.** Its hook
  (`agent/risk_gatekeeper_hook.py`) only fires when something runs the
  `risk_gatekeeper` team, and **no worker / route ever does** (checked
  `entrypoint.sh`, `cli.py`, `server/routes_*`). So a real stage-5 `PASS`
  parks at `BENCHING` forever. This is why I had to drive the hook manually.
  → Needs a `gatekeeper-worker` loop (poll `list_artifacts_by_statuses([BENCHING])`
  → run team → hook), same shape as `capital-allocator-worker`
  (`scheduler_workers.run_capital_allocator_cycle`). **Not built.**
- **G2 — Stage 8 paper store is in-memory only**
  (`broker/performance_store.py` — "non-persistent for v1"). Shadow needs ≥5
  paper days (`min_paper_days`), but data resets on every restart → the ≥5-day
  gate can never actually accumulate. Shadow is currently **effectively
  un-passable in production**. Needs a persistent store (SQLite) or a real
  paper-trading feed.
- **G3 (already logged):** NVDA never completed stages 2–5 in either run — only
  AAPL/MSFT. Not a gap, just incomplete coverage.

---

## ✅ What's LEFT — concrete steps to finish ATS 6→9

### A. Finish now, 0 LLM (recommended — proves all transition code paths)
Prereqs already true: store unified; `art_6862176a8ac7` sits at **PEND**; workers
on 90s cadence.

1. **Stage 7 → ACTIVE (real hook, 0 LLM):** apply the funded decision the
   worker's team would have emitted. From `vinu-components/`:
   ```powershell
   # runs apply_capital_allocator_decision on the live shared store
   Get-Content scripts/ats-fund-stage7.py -Raw | docker compose exec -T agent-api python - --artifact art_6862176a8ac7
   ```
   *(script not yet written — mirror `ats-seed-stage5-6.py`'s hook-call shape;
   feed `{"candidates":[{"artifact_id":..., "funded":true, "amount":6142.86}]}`.)*
   **Confirm:** research HTTP `?status=ACTIVE` returns the artifact; `TickerLedger`
   row `stage=capital_allocator event_type=funded`.
2. **Stage 8 shadow (real 0-LLM worker):** needs a **BENCHING** artifact with
   ≥5 paper days + clearing `meets_promotion_bar` (`deflated_sharpe ≥ 0.95`,
   `holdout_passed`, `stress_passed` — `promotion.py`). So:
   - seed a 2nd BENCHING (e.g. MSFT) with those fields set to pass;
   - `POST /agent/broker/performance/{id} {"daily_returns":[...6+ positive...]}` to the
     **running agent-api** (store is in-memory, must hit the live process);
   - let `shadow-worker` (90s) call `evaluate_all()` → promotes via research
     `/promote`. **Confirm** BENCHING→ACTIVE. *(See G2 — in-memory returns are fine
     for one live-process test, die on restart.)*
3. **Stage 9 monitor (real 0-LLM worker):** seed an **ACTIVE `type=trade_plan`**
   artifact (valid `trade_plan_data`: `symbol`, `direction:"long"`,
   `risk_bands.max_position_size_pct>0`, rules) then let `trade-plan-worker`
   (90s) run `cycle()` → enter/hold vs invalidation_exit. **Confirm**
   `trade_plan_book.db` position + ledger `check/decay/close`.

### B. Finish with the real LLM teams (faithful, needs quota)
1. `VINU_LLM_MODEL` → a live slug (paid `minimax/minimax-m3` after +$10, or a
   working `:free`).
2. Restart agent-api; re-seed BENCHING; drive stage 6 hook → PEND; let the real
   `capital-allocator-worker` fund (1 team call) → ACTIVE; then A.2/A.3 for 8/9.

### C. After any 6→9 pass
- Append rows to `test-status/ledger.md` (new `test_run_id`, e.g.
  `2026-09-07_ats_lifecycle`) with real `ref_id`s + to `manifest.jsonl`.
- Run `scripts/watchdog.py` (W1–W7) over the run.
- **Then** start Full pattern (`full-pattern/`): `VINU_STAGE1_START_DATE=2022-01-01`
  so strategies actually **PASS** stage 5 → the whole 0→9 flows organically (and
  build G1 first, else it stalls at BENCHING).

---

## 🧾 TEMPORARY knobs to REVERT once ATS goes green (all in `.env`, marked)

| Env | ATS value | Production default | File |
|---|---|---|---|
| `VINU_AGENT_PLANNER_INTERVAL` | 60 | 1800 | `.env` ATS block |
| `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL` | 90 | 900 | `.env` ATS block |
| `VINU_LIVE_SHADOW_INTERVAL` | 90 | 3600 | `.env` ATS block (added this session) |
| `VINU_LIVE_TRADE_PLAN_INTERVAL` | 90 | 3600 | `.env` ATS block (added this session) |
| `VINU_CORRELATION_COMPUTE_POLL_INTERVAL_SEC` | 900 | 3600 | `.env` |
| `VINU_RESEARCH_DATA_ROOT=/research-data` (agent/research/portfolio) | shared | was per-`/data` | `docker-compose.yml` (this session — **keep until durable fix per ⚠️ above**) |
| `VINU_STAGE1_START_DATE` | 2026-03-01 (6mo) | 2022-01-01 (Full) | `.env` |
| `VINU_AGENT_WATCHLIST_SEED_TICKERS` | AAPL,MSFT,NVDA | (operator) | `.env` |

## Tooling built this session
- `scripts/ats-seed-stage5-6.py` — seeds BENCHING (real writer) + drives stage 6 (real hook) → PEND. **Ran, verified.**
- (to write) `scripts/ats-fund-stage7.py` — stage 7 hook, 0 LLM.
- `scripts/watchdog.py`, `scripts/collect-timings.py`, `scripts/setup-secrets.ps1` (earlier).

## Related
- `ats-pattern/04-ats-runbook.md` — authoritative stage table (0–9).
- `test-status/ledger.md` — per-run pass/fail evidence; row `2026-09-07_perf_cal_wiring` logs the parallel-summary + calibration + 429 work.
- `../other-our-repo-full-research-features/inefficiencies-A-J.md` — A–J perf ledger; **B built** (parallel summaries), **C, E still open**.
- `../other-our-repo-full-research-features/decisions/08-calibration-decision.md` — screener low-trust overlay now wired (decision 08).
