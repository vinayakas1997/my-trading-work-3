# Learning Over Time - How It Works + Gaps + Extras + Talk Timing (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `20`. Related: `19`, `12`.
Status: Learning step closed with 4 gaps + 3 extras + talk diagram. Full 7. Code steps ready to build next, no code changed yet in this doc.

---

## How learning works today (4 goods, per-trade only)

1. Feedback on every close. File `vinu-live/feedback_loop.py:86`. Writes calibration outcome + pnl attribution angle + personality stats + hypothesis evidence + ticker ledger close-out. Never reopens close. Good.
2. Calibration math exists. Files `vinu-research/calibration.py:22`, `forecast_skill.py:77`. Per angle accuracy, per strategy accuracy. Min window 3 entries. Good.
3. Angle trust overlay in screener. File `vinu-agent/agent/scheduler_workers.py:37` `_angle_trust`. Rated below 0.45 low_trust, unrated no data not low. Observability only, never gate. Fail-open. Good safe.
4. Scans on schedule. Decay ACTIVE and MONITORING, revalidation 30d lookback 180d, regime recompute 1d. Files `vinu-research/scheduled/executor.py:118`, `config.py:162`, `cli.py:146`. Good cadence.

Today only per-trade memory. No monthly lesson. Early Q8 Hermes discussed, never built.

---

## 4 gaps in learning (inefficiencies)

### 1. No long lesson artifact
Per-trade writes exist, no monthly lesson reads 30+ trades + writes 1 lesson artifact next idea reads.
Fix: `hermes-worker 3600s` read-only, write lesson `LESSON` artifact with regime + shape + Sharpe + reasons. `idea_generator` reads lessons before grid. Small worker. Do first with 2. Starts collecting day 1, useful after 30 trades.
Knobs: `VINU_LESSON_ENABLED=true`, `VINU_LESSON_INTERVAL_SEC=3600`, `VINU_LESSON_MIN_TRADES=30`.
Status: Open.

### 2. Calibration not wired to screener filter
Decision `08-calibration-decision.md:8` backlog after A1-A2. Angles below 0.45 still used equally.
Fix: screener fetches calibration before `get_all_angles`, de-prioritizes low_trust, never hard blocks. Same fail-open as trust overlay. Small wire. Do first.
Knobs: `VINU_CALIBRATION_MIN_ACCURACY=0.45`, `VINU_CALIBRATION_MIN_ENTRIES=3` kept.
Status: Open.

### 3. Two decay implementations unreconciled
File `vinu-research/cli.py:569` comment says `_run_decay_scan` vs executor `decay_scan` separate policies. Risk double action or miss.
Fix: reconcile to 1 policy. Keep executor scans, CLI manual only dry-run. Small cleanup. After 1-2 green.
Status: Open.

### 4. No regime lessons + no forgetting
Lessons global, not per regime. Old 2020 lessons mislead 2026.
Fix: lessons per regime bull bear sideways high_vol + decay weight halve every 90 days. Small fields `regime` + `weight` + `updated_at` on lesson artifact. After 1-2 green.
Knobs: `VINU_LESSON_REGIME_ENABLED=true`, `VINU_LESSON_DECAY_HALVE_DAYS=90`.
Status: Open.

---

## 3 advanced from other repos on top

### 5. Qlib RD-Agent loop spec
Source `03-per-repo-deep-dive/qlib-PIT-RD-Agent.md:9`. LLM autonomous factor evolution: propose, test, keep best, mutate next round. Our Thesis Intake Row 11 pattern only, no loop.
Adopt loop spec for `strategy-definitions` generation, not copy code. Medium, after lesson worker green. Copy propose-test-keep-mutate steps + test pattern as-of join.
Knobs: `VINU_RD_LOOP_ENABLED=false` (false now, true after lesson green).
Status: Later. Saved here never lost.

### 6. FinRL bake-off 1 vs 5 + debate Row 6
Source `finrl-5agent.md:20`. 5 brains A2C DDPG PPO TD3 SAC train separate, compare table + buy-hold baseline, best net wins. Adversarial vs single self-verdict `backtest_runner/prompt.md:53`.
Adopt baseline PPO + debate now cheap, 5 full later heavy GPU. Where: `simulator.py:300` env + sweep rank + debate line in self-verdict and risk verdict. Pass only, not every round.
Meaning: round 1 separate compete no talk, round 2+ talk and refine. Together params get right. Single voice blind.
Knobs: `VINU_BAKEOFF_ENABLED=true`, `VINU_BAKEOFF_MODE=ppo1` (ppo1 now, full5 later), `VINU_DEBATE_ENABLED=true`.
Status: Baseline now, full later. Saved here.

### 7. TradeMaster PRIDE star lesson quality
Catalog `02:25`. 8-metric star + Monte Carlo resample for lesson quality. Adopt star in lesson artifact + notebook. Low.
Where: lesson artifact fields TR SR maxDD + resample p-value. Notebook star plot.
Knobs: `VINU_LESSON_PRIDE_ENABLED=true`.
Status: Open. Low. With 1-2 batch.

---

## Talk timing diagram (research talk, live silent, feedback)

```
Research before trade (talk here, LLM)
  idea_generator -> sweep ranked + SELF-VERDICT
  -> bake-off compete separate (round 1, no talk)
  -> debate verdict Row 6 (round 2, talk)
  -> risk_critic PASS or STOP
  -> RD-Agent mutate winner next cycle
  -> BENCHING 6 (1D top3 + 1H top3)
       |
       v
Paper 5 to 10 days (no talk, numbers only)
  rehearsal 7d -> shadow paper Sharpe + degradation 0.5
       |
       v
Live during trade (silent, zero LLM)
  monitor orchestrator.py:1 mechanical only
  invalidation, breaker, rebalance, reconcile
  no debate, no LLM, frozen plan JSON only
       |
       v
After close (talk resumes for next trade)
  feedback_loop.py:86 calibration + ledger + hypothesis
  -> lesson worker reads 30+ -> next research reads lesson
```

Rule: talk before trade in research, silent during trade in live, talk again after close for next trade. Live speed + deterministic. Frozen plan only.

---

## Knobs full list for learning (add to 10 later build)

- Lesson: `VINU_LESSON_ENABLED`, `VINU_LESSON_INTERVAL_SEC=3600`, `VINU_LESSON_MIN_TRADES=30`, `VINU_LESSON_REGIME_ENABLED`, `VINU_LESSON_DECAY_HALVE_DAYS=90`, `VINU_LESSON_PRIDE_ENABLED`.
- Calibration kept: `VINU_CALIBRATION_MIN_ACCURACY=0.45`, `VINU_CALIBRATION_MIN_ENTRIES=3`.
- Scans kept: revalidation 30d lookback 180d, regime 1d, decay 24h. Single policy after reconcile.
- Bakeoff debate RD: `VINU_BAKEOFF_ENABLED`, `VINU_BAKEOFF_MODE`, `VINU_DEBATE_ENABLED`, `VINU_RD_LOOP_ENABLED`.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives lessons per interval, no extra knob. New interval lessons appear auto.

---

## Order to build (lesson + calibration first, closed 7)

1. Lesson worker + calibration wire. 1-2 together. Small. Memory starts day 1. Do first.
2. Decay reconcile + regime lessons forgetting + PRIDE star. 3-4 + 7 together. After 1 green. Cleanup + precision.
3. Baseline PPO + debate. 6 baseline now. After 2 green. Cheap adversarial on PASS only.
4. RD loop + full 5-agent. 5-6 later. After 3 green + 30 trades + GPU budget. Medium heavy.
5. Test: lesson writes after 30, screener de-prioritizes low_trust, single decay policy, regime lessons separate, forgetting halves 90d, PPO compares on PASS, debate cites table, RD mutates next cycle.

After 1-5, learning done. Full pipeline 0-9 + learning docs 01 to 20 closed.

---
Link: Significance skills workers is in `21-significance-skills.md`. Infra secrets docker is in `22-infra-secrets-docker.md`. Runbooks ATS Full is in `23-runbooks-ats-full.md`. 20 -> 21 -> 22 -> 23 = learning -> workers -> infra -> runbooks closed. Full docs 01 to 23 closed.

---

## Where learn used - impact map (5 places, when effective)

1. Next idea choice. Lesson `LESSON` regime + shape + Sharpe. `idea_generator` reads before grid. File `teams/research/agents/idea_generator/prompt.md:10`. Impact: stops repeat loser. Example lesson `crossover fails sideways 3 times` -> next picks `rsi`. Saves 190s + LLM per avoided fail. Trigger: 30+ trades. Before that collect only.
2. Screener angle trust. Accuracy per angle. Files `calibration.py:22`, `scheduler_workers.py:37`. De-prioritize below 0.45. Impact: `kronos 0.3` ignored, `arima 0.7` weighted. Better agree and diverge. Trigger: 3+ rated entries per angle. Today unrated no effect.
3. Thesis + hypothesis history. Thesis + evidence + invalidation. File `theory_reviewer/prompt.md:22`. THGATE + reviewer block duplicate bad thesis. Impact: saves LLM call per blocked duplicate. Trigger: 5+ hypotheses stored. Effective early.
4. Portfolio tilts + sizing. Accuracy per artifact. File `service.py:418`. High tilts up 0.3, low down. Regime lessons per bull and bear. Impact: money to proven shapes + regimes. Trigger: 5+ entries per strategy. Today neutral 1.0.
5. Decay + revalidation + monitor pause. 30d + 1d + decay scan. Files `scheduled/executor.py:118`, `config.py:162`. Rank2 promotes on 0.5 drop. 3-day pause cuts live 30 to 3 days. Impact: saves real drawdown. Trigger: ACTIVE exists. Today idle, no ACTIVE.

Not effective when: day 1 to 29 collect only, live silent no LLM intraday, single lucky needs purge `08` first. Honest limits. Worth yes after triggers. You asked worth yes or no, answer yes with triggers above.

---

## Vector decision: SQLite now, sqlite-vec later at 1000 (memo hindsight not core)

Today memory tiny. Hypotheses 10s, lessons 0, summaries 3. SQLite exact + Jaccard 0.5 words works. File `thesis_intake_gate.py:31`. Cheap deterministic no server. Vector overkill for 100 rows.

Vector like memo or hindsight-ai helps later at 1000+ lessons across regimes. Keyword misses meaning. Example gate blocks `buy after earnings` but allows `purchase post results` same meaning. Jaccard 0.2 misses, vector 0.9 catches. Lesson recall by meaning: query `sideways rsi` gets `range mean-reversion` even words differ. Hindsight pattern auto log + recall same as lesson worker + registry, just vector recall vs symbol query.

Decision 2 stages, set once:
- Now: keep SQLite + tags. THGATE Jaccard + tag + regime match catches 80 percent, no infra. Lesson writes tags regime shape ticker. Query by tags + symbol. Enough to 1000 rows.
- Later at 1000 trigger: add `sqlite-vec` in-process, 1 table lesson_embeddings 384-dim local model, top 3 cosine + symbol filter. Chroma or Qdrant server only if multi-container shared vectors needed. Memo or hindsight spike optional hosted UI, not core.
- Tradeoff: vector now = server + 0.5s latency + nondeterministic for tiny gain. Not worth. Vector later = real gain when meaning matters. Worth after ACTIVE 10 + lessons 100+.
- Knobs: `VINU_LESSON_VECTOR_ENABLED=false`, `VINU_LESSON_VECTOR_THRESHOLD=1000`, `VINU_LESSON_TAGS_ENABLED=true`. Later env flip only.

---

## All covered proof (nothing missed for learning)

- Feedback `feedback_loop.py:86,121,135` 5 writes covered.
- Calibration `calibration.py:22`, `forecast_skill.py:77`, trust `scheduler_workers.py:37`, decision `08-calibration-decision.md:8` covered gaps 2.
- Scans `scheduled/executor.py:118`, `config.py:162`, `cli.py:146,569` covered gap 3 + cadence.
- Hypothesis registry + judgment store covered stores.
- Early Q8 Hermes lesson discussed, now gap 1 worker concrete.
- Repos mapped: Qlib RD-Agent 5 here, FinRL bake-off 6 here, TradeMaster PRIDE 7 here. Qlib PIT done 08/18, Freqtrade pairlist lookahead done 08/18, Nautilus fills done 12/16, PyPortfolioOpt HRP done 13/19, Lean cycle done 15, wraquant blend done 19, cpz-quant NCO done 19. No new repo needed.
- Ledger `inefficiencies-A-J.md` H ref_id, D cache kept. Slices `04` A1 rehearsal done 12, B gateway freeze dry-run kept 13/16/18.
- 09 top3, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full, 14 storage full, 15 monitor closed, 16 broker closed, 17 UI closed, 18 data closed, 19 portfolio regimes closed kept. 20 closes learning. Pipeline 0-9 + learning full chain closed.
