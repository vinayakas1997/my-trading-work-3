# Env Knobs - Full Control, No Code Change (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `10`. Related: `07`, `08`, `09`.
Rule: Set once, touch rarely. Not confusing. Add `15min` later = 1 env change + restart, no rebuild.

---

## Why full knobs, not minimalist

Today `1d` is hard in prompt + config. Adding `15min` needs code edit + rebuild. Too hard.
With knobs, all control in `.env` + `.env-example`. Code reads via `load_config`. No hard values.
Full 18 knobs, not 6 minimalist. We do not touch daily, so not confusing. You said ok.

Where to put later in build:
- `.env-example:206` new section `--- vinu-research sweep knobs ---` with defaults + comments.
- `.env` copy same values with real settings.
- `vinu-research/config.py:192` `load_config` read new env, same pattern as existing.
- `vinu-agent/config.py:41` `AgentConfig` read same for writer + planner.
- `sweep_grid.py:86` read TOP_N + USE_VECTORBT. `comparison.py:19` read DIVERSITY. `correlation_gate.py:34` read threshold.
- `backtest_runner/prompt.md:12` manager injects INTERVALS list into task, not hard `1d`.

---

## Full 18 knobs table

### Sweep control (9)

1. `VINU_SWEEP_INTERVALS=1d,1H,15min`
   What: comma list which intervals sweep runs. 3 formats now. 1D + 1H + 15min = 9 per ticker with top 3 each. You asked 9, correct.
   Default: `1d,1H,15min`. When to change: add `5min` or `4H` here only, no code.
2. `VINU_SWEEP_TOP_N_PER_INTERVAL=3`
   What: top N kept per format. 3 per 1D + 3 per 1H + 3 per 15min = 9 per ticker. 27 for 3 tickers.
   Default: `3`. When: change to 5 for wider backup (15 per ticker).
3. `VINU_RESEARCH_SWEEP_GRID_MAX_POINTS=20`
   What: max points per round. Already exists in `sweep_grid.py:37`. Keep.
   Default: `20`. When: lower to 10 to save cost.
4. `VINU_SWEEP_USE_VECTORBT=true`
   What: true = fast 20 points 10s vector. false = slow loop rollback.
   Default: `true`. When: false only to debug.
5. `VINU_SWEEP_USE_HYPEROPT=true`
   What: true = smart Bayesian search. false = brute grid.
   Default: `true`. When: false for pure brute compare.
6. `VINU_SWEEP_HYPEROPT_MAX_POINTS=8`
   What: smart points count per round. 8 smart, not 20 brute.
   Default: `8`. When: 12 for wider search.
7. `VINU_SWEEP_PAIRLIST_ENABLED=true`
   What: drop illiquid tickers by volume before sweep.
   Default: `true`. Pair: `VINU_SWEEP_MIN_VOLUME=1000000`.
8. `VINU_SWEEP_DIVERSITY_REQUIRED=true`
   What: top 3 must be different shapes. Not 3 crossover variants.
   Default: `true`. When: false only to test.
9. `VINU_SWEEP_REGIME_TAG_ENABLED=true`
   What: tag each of the 6 with trend, range, high-vol.
   Default: `true`. When: false to hide regime.

### Validation control (6)

10. `VINU_RESEARCH_WF_GAP_DAYS=5`
    Already exists. Keep for purge gap. Default `5`.
11. `VINU_SWEEP_PURGE_ENABLED=true`
    Purged + embargo CV. Honest PBO. Default `true`.
12. `VINU_SWEEP_TRIPLE_BARRIER_ENABLED=true`
    Take-profit, stop-loss, max-hold label. Default `true`.
13. `VINU_SWEEP_LOOKAHEAD_GUARD_ENABLED=true`
    Scan winner for future leak `data[i+1]`. Fail if leak. Default `true`.
14. `VINU_SWEEP_MIN_SUCCEEDS_FOR_PASS=2`
    Require 2+ succeeds for PASS. Stops single lucky PASS. Default `2`.
15. `VINU_RESEARCH_PROMOTION_DSR_THRESHOLD=0.95`
    Already exists. Keep. Default `0.95`.
16. `VINU_RESEARCH_PROMOTION_CORRELATION_THRESHOLD=0.85`
    Already exists. Top 3 must not correlate to ACTIVE above this. Default `0.85`.

### Rehearsal + lifecycle (4)

17. `VINU_RESEARCH_PAPER_REHEARSAL_ENABLED=true`
    Already exists. 7-day rehearsal before BENCHING. Keep.
    Pair: `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS=7`. Already exists.
18. `VINU_SWEEP_FREEZE_REQUIRED=true`
    Each of the 6 links to data hash. No hash = no BENCHING. Default `true`.
19. `VINU_RESEARCH_REVALIDATION_INTERVAL_DAYS=30`
    Already exists. Winner decays, backup promotes every 30 days. Default `30`.
20. `VINU_SWEEP_ENSEMBLE_ENABLED=false`
    Mix top 3, not winner only. false now, true after green. Default `false`.
21. `VINU_SWEEP_RANKING_VIEW_ENABLED=true`
    Notebook rank table on/off. Default `true`.

### Paper-days knobs (new, see 11 file ok)

22. `VINU_SHADOW_MIN_PAPER_DAYS=5`
    Change to `10` any time + restart. No rebuild. Default `5`.
23. `VINU_SHADOW_MIN_PAPER_DAYS_1D=10` + `VINU_SHADOW_MIN_PAPER_DAYS_1H=5`
    Per interval proof. 1D longer, 1H faster. Best balance. Wire into `ShadowEvaluator.__init__` via config.
    File `vinu-live/vinu_live/shadow_evaluator.py:28`. Rehearsal knob already exists `VINU_RESEARCH_PAPER_REHEARSAL_LOOKBACK_DAYS=7`.
    Rule: paper all 6 per ticker, promote best forward paper `paper_sharpe > 0` + `degradation <= 0.5`. See `11-paper-all-6-live.md`.

### Risk allocation knobs (see 13 file ok)

24. Per strategy: `VINU_AGENT_POSITION_SIZING_METHOD=fractional_kelly`, `VINU_AGENT_KELLY_FRACTION=0.25`, `VINU_AGENT_RISK_PER_TRADE_PCT=0.02`, `VINU_AGENT_ATR_STOP_MULTIPLE=2.0`.
25. Batch: `VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET=100000`, intervals 900 or 60/90 fast Full.
26. Tail + vol Now: `VINU_RISK_CVAR_ENABLED=true`, `VINU_RISK_CVAR_THRESHOLD=0.03`, `VINU_RISK_VOL_TARGET_ENABLED=true`, `VINU_RISK_VOL_TARGET=0.15`, `VINU_RISK_VOL_LOOKBACK_DAYS=21`.
27. BL + HRP Later auto: `VINU_ALLOCATOR_ADVANCED_ENABLED=auto`, `MIN_TICKERS=4`, `MIN_STRATEGIES=18`, `MIN_TRADES=30`, `MIN_LIVE_DAYS=60`, `BL_TAU=0.05`, `L2_GAMMA=0.1`. Manual true/false override. See `13-risk-allocation-full.md`.

### Learning + vector knobs (see 20 file ok)

28. Lesson triggers kept: `VINU_LESSON_ENABLED=true`, `VINU_LESSON_INTERVAL_SEC=3600`, `VINU_LESSON_MIN_TRADES=30`, `VINU_LESSON_REGIME_ENABLED=true`, `VINU_LESSON_DECAY_HALVE_DAYS=90`, `VINU_LESSON_PRIDE_ENABLED=true`.
29. Vector later: `VINU_LESSON_VECTOR_ENABLED=false`, `VINU_LESSON_VECTOR_THRESHOLD=1000`, `VINU_LESSON_TAGS_ENABLED=true`. SQLite tags now to 1000 rows, sqlite-vec later top 3 cosine. Chroma server only if shared needed.
30. Bakeoff debate RD kept: `VINU_BAKEOFF_ENABLED=true`, `VINU_BAKEOFF_MODE=ppo1`, `VINU_DEBATE_ENABLED=true`, `VINU_RD_LOOP_ENABLED=false` (false now true after lesson green).

### Retention pruning 90d dry-run (see 13 file ok)

31. `VINU_RETENTION_REJECTED_DAYS=90`, `VINU_RETENTION_SIM_EQUITY_DAYS=90`, `VINU_RETENTION_SIM_TRADES_SUMMARY=true`, `VINU_LEDGER_RETENTION_DAYS=365`, `VINU_RETENTION_DRY_RUN=true`.
32. Rule: keep rejected BENCHING + ledger REJECTED + sim + team run day 1. After 90d + fail 2x move DISABLED keep summary delete equity + weights bulk. Dry-run true logs only first 2 weeks.

### Workers + infra + runbooks knobs (see 21 22 23 files ok)

34. Significance delivery audit: `VINU_SIGNIFICANCE_INTERVAL_SEC=900`, `TELEGRAM_TOKEN`, `VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID`, `DISCORD_TOKEN`, `VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID`, `VINU_SIGNIFICANCE_MUTE_HOURS=24`, `VINU_SKILL_AUDIT_INTERVAL_SEC=3600`, `VINU_SKILL_VERSION_PIN=true`.
35. Infra secrets docker: ports 8080-8091 kept, `/data` roots kept, `VINU_HTTP_RETRY_SEC=10`, `VINU_HTTP_RETRY_COUNT=3`, `VINU_MODELS_DIR=/models` kept. Secrets files only for keys, `.env` URLs intervals only. `setup-secrets.sh --check` ready.
36. Runbooks mode switch: `VINU_STAGE1_START_DATE` ATS 2026-06-17 short vs Full 2022-01-01, `VINU_TIER2_PERIOD_MONTHS=3`, `VINU_AGENT_WATCHLIST_SEED_TICKERS=AAPL,MSFT,NVDA`, timers fast 60/60/90/90/90 kept. Same `VINU_SWEEP_INTERVALS` drives ATS + Full.

Note: count is 21 lines with pairs, core 18 knobs. Full, not minimalist. Set once.

---

## Example future change (no code)

Need `15min` with 3 formats now 9 per ticker:
1. `VINU_SWEEP_INTERVALS=1d,1H,15min` set. Restart agent + research. Done. No rebuild.
2. Sweep now runs 1D top 3 + 1H top 3 + 15min top 3 = 9 per ticker. 27 for 3 tickers. Same paper all 9 + promote best forward paper rule `11` file.
3. Report shows `15min 28/28` alongside `1D 27/27`, `1H 28/28`. 15min significance session + day-vol + near-live context `09` section. Fills honest required `16` gap 1 for 15min live.

Need 5 per format later:
1. Change `VINU_SWEEP_TOP_N_PER_INTERVAL=3` to `5`. Restart. Done.

---

## Order to wire in code (later build, one by one)

1. Add 10 new env to `.env-example` section + `.env` values.
2. Extend `vinu-research/config.py:192` + `vinu-agent/config.py:41` to read them.
3. Wire `INTERVALS` into manager task + `sweep_grid.py:86` loop per interval.
4. Wire `TOP_N` into `research_artifact_writer.py:43` write 3, not 1.
5. Wire flags into `comparison.py:19`, `pbo.py`, `correlation_gate.py:34`, `freeze.py`, `scheduled/executor.py:148`.
6. Test: change INTERVALS, restart, verify `15min 28/28` appears with no code edit.

---

## All covered proof

- 07 seven gaps -> knobs fix No.1 intervals, No.2 custom grid, No.3 vectorbt speed.
- 08 1+2 + 5 logics -> knobs 4-13 cover all.
- 09 top 3 + 3 extra + final 3 -> knobs 2, 8, 9, 18-21 cover all.
- Existing knobs kept: grid max, WF gap, DSR, correlation, rehearsal, revalidation. No duplicate.
- Nothing left for sweep step after this file.
