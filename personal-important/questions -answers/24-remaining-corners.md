# Remaining Corners - Entrypoints First + 4 Next One By One (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `24`. Related: `21`, `22`, `23`.
Status: Section 1 entrypoints closed. Sections 2-5 outline saved, details one by one next. No code changed yet in this doc.

---

## Section 1: Entrypoints + workers wiring (closed)

Rule: background workers + foreground serve owns lifecycle. Same fix shape everywhere: real loop existed, no caller, entrypoint adds caller. Phase 9 scheduler-wiring + Phase 5 monitor-extend.

Table: container, workers, intervals default + fast Full, order, file line.

| Container | Workers background | Intervals default / fast Full | Order | File |
|---|---|---|---|---|
| agent-api 8086 | skill-audit-worker, planner-worker, significance-worker, capital-allocator-worker, risk-gatekeeper-worker + mandate tmpfs create | 3600 / 3600, 1800 / 60, 900 / 900, 900 / 90, 900 / 60 | skill -> planner -> significance -> capital -> risk, then mandate, then serve owns lifecycle | `vinu-agent/entrypoint.sh:13` |
| live-api 8091 | vinu-live-worker, trade-plan-worker, feedback-worker, shadow-worker | 3600 / 3600, 90 / 90, always / always, 90 / 90 | live -> trade-plan -> feedback -> shadow, then serve owns lifecycle | `vinu-live/entrypoint.sh:14` |
| portfolio-api 8090 | monitor | always / always | monitor, then serve | `vinu-portfolio/entrypoint.sh:4` |
| research-api 8087 | schedule-decay, schedule-freshness (revalidation + regime) | 24h / 24h, 1h + 24h / 1h + 24h | decay + freshness, then serve | `vinu-research/entrypoint.sh:4` |
| quant-core-api 8084 | none, stateless pure request response | none | serve only | `vinu-quant-core/Dockerfile:3` |
| news 8080, stock 8081, tools 8082, initial 8083 | ingest + compute polls per service | news 600, stock 60, features on-demand, initial compute 3600 | worker then serve per Dockerfile ENTRYPOINT | `*/Dockerfile`, `*/entrypoint.sh` |

Depends healthy chain in compose: stock + news -> features + initial -> quant-core + research -> portfolio + agent -> live. No start before healthy. Restart `unless-stopped`. Agent tmpfs `/nonexistent:rw,mode=1777,exec` fixed 06:51 loop. Same pattern live workers.

Gaps + suggestions for section 1 (3 small, docs now script Later):

1. Restart order table missing. Planner needs skill audit done first, no wait today. Fix docs table above now. Code wait later infra window. Small docs. Done in this file.
2. No supervisor restart on worker crash. `&` dies silent, serve stays healthy. Lean and Nautilus supervisor restarts + log rotation. Fix Later: tiny supervisor loop or `wait -n` + log per worker + health flag. Small script. Docs now, script Later infra window. Agreed docs now script Later.
3. `set -e` does not watch background. Foreground `exec serve` last kept correct. Document kept. No change now.

Knobs for section 1 (kept, no new): `PLANNER 1800/60`, `RISK 900/60`, `CAPITAL 900/90` + budget, `SIGNIFICANCE 900`, `SKILL 3600`, `TRADE 90`, `SHADOW 90`, `FEEDBACK` always, `DECAY 24h`, `FRESHNESS 1h/24h`, `MONITOR` always, `COMPUTE 3600`, `NEWS 600`, `STOCK 60`. Same as `10` + `22`. No duplicate.

Other repos for entrypoints: Lean supervisor + Nautilus persistence + Docker `unless-stopped` already set. Match. Nothing more needed.

---

## Section 2: Scripts + setup (outline, details next one by one)

- `scripts/setup-secrets.sh --check` ready before up. Secrets files only for keys, `.env` URLs intervals only. File `22` doc kept.
- `run_pipeline.py` watchlist POST tickers. File `run_pipeline.py:303`. Order: seed watchlist -> planner cold-start summary -> research. When to run: new ticker add + ATS before Full.
- `run_month_replay.py` health check `GET /health`. Order: health all green -> ATS 1 ticker -> Full.
- Details + knobs + order table next message. Status: outline saved, not closed.

## Section 3: Tools indicators mismatch decision (outline, details next)

- Catalog 24 look vs backtest-safe 10 mergeable. `supertrend cmf bollinger` fail in code even though real in features. Files `idea_generator/prompt.md:26`, `backtest_tool.py:53`.
- Decision needed: expand mergeable to 24 with engine support, or keep 10 + docs warning + prompt guard. Small decision, medium if expand.
- Details + decision doc next message. Status: outline saved, not closed.

## Section 4: Tests index (outline, details next)

- Each doc 07-24 has order + acceptance, but no single test map file:line test per knob. `pytest` lines scattered `batch-*.md` + `vinu-*/tests/test_*.py`.
- Need 1 table: knob -> test file:line -> command -> expected. Small index docs.
- Details next message. Status: outline saved, not closed.

## Section 5: Unwanted + logs cleanup (outline, details next)

- `unwanted/`, `logs/`, `personal-important/`, `.kilo/` never triaged keep vs delete vs archive. Small cleanup, prevents confusion.
- Rule: `unwanted` archive zip + delete after 23 docs closed, `logs` 30d prune, `personal-important` keep gitignored, `.kilo` keep agent local.
- Details + commands next message. Status: outline saved, not closed.

---

## Order (one by one, like 7 points)

1. Section 1 entrypoints closed now. Done above.
2. Section 2 scripts next. Then 3 indicators decision. Then 4 tests index. Then 5 cleanup.
3. Each section: check files, gaps 2-3 small, other repos if needed, knobs, order, proof. Same pattern as 7 points.
4. After 2-5, `24` full closed. Full docs 01 to 24 closed. Then code builds.

---

## All covered proof for section 1 (nothing missed for entrypoints)

- Agent `entrypoint.sh:13-59` 5 workers + mandate + serve covered.
- Live `entrypoint.sh:14-23` 4 workers + serve covered.
- Portfolio `entrypoint.sh:4` monitor + serve covered. Drawdown monitor fix referenced in agent/live entrypoints kept.
- Research `entrypoint.sh:4` decay + freshness covered. 2 decays unreconciled kept `20` gap 3.
- Quant-core `Dockerfile:3` stateless no worker covered correct.
- News stock tools initial Dockerfiles ENTRYPOINT covered pattern, details in section 2-4 later if needed.
- Compose depends healthy + restart + tmpfs fix 06:51 kept `22`.
- Supervisor Lean Nautilus pattern noted Later, docs now agreed.

---
Link: Money gate real money 6 gaps + 2 top is in `25-money-gate.md`. 24 -> 25 = corners -> money gate closed. Full docs 01 to 25 closed.
