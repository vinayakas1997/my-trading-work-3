# Risk Allocation Full - Meaning + Advanced + Auto Guard (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `13`. Related: `09`, `10`, `11`, `12`.
Status: Risk allocation step closed. Nothing missed after execution guards included.

---

## What is risk allocation? Meaning

Risk allocation = how much money each strategy gets, given risk limits. Not new strategy. Same 6 strategies. Only money split. Link is same `artifact_id`.

Two parts:

1. Per strategy how much it deserves. Risk gatekeeper.
- Inputs: win rate + payoff from backtest of that one strategy + account equity.
- Formula: `fractional_kelly 0.25`. File `vinu-agent/vinu_agent/agent/position_sizing.py:15`. Full Kelly `(p*b - q)/b` clamped >= 0, times 0.25 quarter. Zero edge = 0 size.
- Fallbacks: `fixed_fractional` capital x 0.02 (1-2% rule), `atr_stop` (equity x 0.02)/(atr x 2) x entry. File `position_sizing.py:20`.
- Cap: concentration headroom `min(20% portfolio_value, buying_power) - held`. File `teams/risk_gatekeeper/agents/exposure_reviewer/prompt.md:36`. Approved size = lower of formula vs headroom.
- Verdict: `APPROVED -> PEND` with `approved_size` + `sizing_inputs`, or `REJECTED` 0. File `teams/risk_gatekeeper/manager_prompt.md:29`.
- Fail rule: broker error = REJECTED fail-closed. Concentration unavailable = fall back to raw portfolio fail-open. Never invent edge.

2. Batch how much it gets from shared budget. Capital allocator.
- Inputs: all PEND ids at once + budget 100000. File `vinu-agent/config.py:108`.
- Engine: `vinu-portfolio` risk-parity + correlation vs active book. File `teams/capital_allocator/agents/allocation_analyst/prompt.md:9`. Correlated candidates sized down, not ranked alone.
- Cap: `min(portfolio size, approved_size)`. Portfolio can size DOWN only, never expand.
- Verdict: `PEND -> ACTIVE` funded amount + reason, or `PENDBLOCK` with reason. Rebalance unwind only if ACTIVE weaker by calibration, monitor can decline. File `teams/capital_allocator/manager_prompt.md:25`.
- Fail rule: portfolio unreachable = nothing funded this cycle, wait next 900s. Never guess funding.

So allocation = approved_size per strategy + funded amount per batch. No separate code stored. Strategy code same from sweep winner.

---

## We covered already (keep as is, good)

- Kelly quarter + fixed + ATR per strategy. Decision `decisions/05-sizing-decision.md:7`. Env `VINU_AGENT_POSITION_SIZING_METHOD`, `VINU_AGENT_KELLY_FRACTION=0.25`, `VINU_AGENT_RISK_PER_TRADE_PCT=0.02`. Matches web safe default quarter-Kelly.
- Portfolio risk parity + regime tilt + outcome tilt + vol-target 15% cap 1x. File `decisions/05-sizing-decision.md:9`. Matches web production hybrid: parity baseline + Kelly tilt capped.
- Caps: K=3 shared, iters 5, holdout 20% gap 5d, walk 3 expanding, rehearsal 7d degrade 0.5. File `decisions/07-caps-decision.md:7`. All env knobs, tunable live.
- Web hybrid confirms combo right: parity robust when edge noisy, Kelly wins when edge well-measured ratio > 3. Our 1 loss = noisy, so parity baseline correct now.

---

## Now 1+2: tail + dynamic vol (small, high safety, do first)

### 1. Tail risk gate VaR / CVaR
Web `cpz-quant + tradecraft` has mean-CVaR, CDaR, Ulcer. We check maxDD -0.25 only, no CVaR 95%.
Fix: block if CVaR 95% over 3% daily or CDaR over threshold. Add gate in risk gatekeeper exposure reviewer after concentration check.
Knobs: `VINU_RISK_CVAR_ENABLED=true`, `VINU_RISK_CVAR_THRESHOLD=0.03`, `VINU_RISK_CVAR_CONFIDENCE=0.95`.
Status: Open. Small gate.

### 2. Volatility targeting dynamic
Web: static size = varying risk. We have static vol-target 15% cap. Need dynamic: `position = target_vol / current_vol`. High vol halves size auto. Low vol raises within 1x cap.
Fix: add to `position_sizing.py` after Kelly. Use 21-day rolling vol like `regime.py:12`.
Knobs: `VINU_RISK_VOL_TARGET_ENABLED=true`, `VINU_RISK_VOL_TARGET=0.15`, `VINU_RISK_VOL_LOOKBACK_DAYS=21`.
Status: Open. Small formula.

---

## Later 3+4: BL + HRP (needs 4 guards, saved never lost)

### 3. Black-Litterman views
Web + `pyportfolioopt` + catalog `02:18`. Thesis views as BL views with confidence. Today thesis goes to research loop, not allocator weights.
Needs: view confidence calibration (need 30+ trades, file `decisions/08-calibration-decision.md` unrated until 3 entries), market equilibrium prior 5-20y, covariance stable.
Problem if now: blends noise, smart weights random, delays Full PASS, hides bad edge.
Trigger: start when 4 guards all yes (see below). Then blend prior parity + views by confidence.
Knobs: `VINU_ALLOCATOR_BL_ENABLED=auto`, `VINU_ALLOCATOR_BL_TAU=0.05`.
Status: Later. Saved here, never lost. Start after ACTIVE 3 + paper 10d green.

### 4. HRP + L2 + turnover
Catalog `02:18` + web HRP stable no inversion. Today inverse-vol parity, no clustering, no L2, no turnover cost.
Needs: 18 strategies to cluster (3 x 6), live covariance 60d (file `config.py:115`), rebalance logs to tune gamma.
Problem if now: 3 tickers 1 strategy = 1 cluster = same as equal weight, extra code, slows PASS. Current parity enough per `05-sizing-decision.md:24`.
Trigger: same 4 guards. Then switch parity to HRP when guard passes, add `L2 gamma 0.1`, turnover cap.
Knobs: `VINU_ALLOCATOR_HRP_ENABLED=auto`, `VINU_ALLOCATOR_L2_GAMMA=0.1`, `VINU_ALLOCATOR_TURNOVER_CAP=0.5`.
Status: Later. Saved here. Decision first, code next.

---

## Auto guard: tickers > 3 starts, with 4-condition safety

Your rule: tickers more than 3 auto starts. Yes with safety fix. Tickers alone risky early (4 tickers day 1, trades 1, live 0 = noisy covariance, fake clusters).

Full auto 4 guards, all must yes. Set once, never touch:
- `VINU_ALLOCATOR_ADVANCED_ENABLED=auto`: auto, true force now, false force off debug.
- `VINU_ALLOCATOR_MIN_TICKERS=4`: your rule, more than 3.
- `VINU_ALLOCATOR_MIN_STRATEGIES=18`: 3 x 6 BENCHING for cluster size.
- `VINU_ALLOCATOR_MIN_TRADES=30`: closed trades for calibration rated.
- `VINU_ALLOCATOR_MIN_LIVE_DAYS=60`: live covariance stable, same as beta hedge 60d.

Logic each cycle: count tickers from TickerSummaryStore, BENCHING from strategy_store, closed from TickerLedger, live days from book. All 4 yes = activate BL + HRP. Any 1 no = stay Kelly + parity. Fail-open to old on lookup fail.

Wire later: `vinu-agent/config.py:110` read knobs, `vinu-portfolio/service.py:210` switch, thesis views to BL when guard passes.

---

## Execution guards after funding (missed earlier, added now so zero missed)

1. `order_guard`: size, price band, active-artifact check before live order. Blocks oversize or no ACTIVE.
2. `kill_switch`: halt blocks even risk-reducing? Policy doc needed. Halt = no new orders, monitor can still close? Pin policy.
3. Mandate `mandate.yaml`: `max_position_pct 0.25`, `max_order_value 50000`, `max_daily_orders 20`, `max_daily_trade_volume 200000`. Caps live, not research.
4. Rebalance unwind: capital asks, monitor decides, can decline if profitable or kill engaged. File `capital_allocator/manager_prompt.md:25`.
5. `allocation_tool` retry: portfolio hiccup = funding skipped to next 900s. Add retry 30 to 10s + 1s like `inefficiencies-A-J.md:F` built pattern. Fail-closed, never guess.

---

## Knobs full list for risk (add to 10 file too)

Per strategy: `VINU_AGENT_POSITION_SIZING_METHOD=fractional_kelly`, `VINU_AGENT_KELLY_FRACTION=0.25`, `VINU_AGENT_RISK_PER_TRADE_PCT=0.02`, `VINU_AGENT_ATR_STOP_MULTIPLE=2.0`.
Batch: `VINU_AGENT_CAPITAL_ALLOCATOR_BUDGET=100000`, `VINU_AGENT_CAPITAL_ALLOCATOR_INTERVAL=900`, `VINU_AGENT_RISK_GATEKEEPER_INTERVAL=900` (or 60/90 fast Full).
Tail + vol Now: `VINU_RISK_CVAR_ENABLED`, `VINU_RISK_CVAR_THRESHOLD`, `VINU_RISK_VOL_TARGET_ENABLED`, `VINU_RISK_VOL_TARGET`, `VINU_RISK_VOL_LOOKBACK_DAYS`.
BL + HRP Later: `VINU_ALLOCATOR_BL_ENABLED`, `VINU_ALLOCATOR_HRP_ENABLED`, `VINU_ALLOCATOR_L2_GAMMA`, `VINU_ALLOCATOR_ADVANCED_ENABLED`, `MIN_TICKERS`, `MIN_STRATEGIES`, `MIN_TRADES`, `MIN_LIVE_DAYS`.

---

## Retention: keep rejected, prune bulk 90d keep summary (no simply delete)

Rule decided: rejected stays, not deleted day 1. Prune bulk after 90 days. Disk safe + learning kept. You said pruning good.

- Keep on reject: artifact stays BENCHING + ledger REJECTED row + sim folder + team run. Files `risk_gatekeeper_hook.py:6`, `results.py:42`. Needed for significance repeated rejection, lessons, K-cap, audit. Never delete on reject.
- Prune bulk after 90d + revalidation fail 2x: move to DISABLED terminal. Keep 1 summary row + metrics + reason + hash. Delete `equity.parquet` + `weights.parquet` bulk. Keep trades count + `meta.json` + metrics summary. Same as data 90d rule `18` doc step 8.
- Ledger + team runs: ledger keep 365d summary, team runs keep header + verdict prune large LLM text after 90d or export parquet first. `ref_id` still resolves via `verify_ref_id` fail-open.
- Dry-run true first 2 weeks logs what would delete, no delete. False deletes bulk after you approve logs.
- Knobs: `VINU_RETENTION_REJECTED_DAYS=90`, `VINU_RETENTION_SIM_EQUITY_DAYS=90`, `VINU_RETENTION_SIM_TRADES_SUMMARY=true`, `VINU_LEDGER_RETENTION_DAYS=365`, `VINU_RETENTION_DRY_RUN=true`.
- Simply delete-all rejected: disk tiny save MBs, learning lost forever, repeats bad crossover. Do not do. Prune-bulk-90d chosen.

---

## Order to build (closed, no left-out)

1. Tail CVaR + dynamic vol. Small, high safety. Do first.
2. Paper-days per interval already planned 10/5. Keep.
3. Auto 4-guard knobs + counts wiring. Set once.
4. BL + HRP when 4 guards green. After ACTIVE 3 + paper 10d + live 60d.
5. Execution guards policy pin: order_guard bands, kill policy, mandate caps, unwind rule, retry.

After 1-5, risk allocation done. Next is live monitor scale. Different step.

---

## All covered proof (nothing missed)

- Prompts `risk_gatekeeper/manager_prompt.md`, `exposure_reviewer/prompt.md`, `capital_allocator/manager_prompt.md`, `allocation_analyst/prompt.md` covered meaning + fail rules.
- Math `position_sizing.py:15` Kelly + fallbacks covered.
- Decisions `05-sizing-decision.md`, `07-caps-decision.md` covered combo + caps.
- Web ML4Trading + wraquant + Kelly + risk parity vs Kelly + tradecraft + cpz-quant covered hybrid, MVO shrinkage, HRP, BL, VaR/CVaR, vol targeting, turnover, cardinality.
- Catalog `02:17-26` mapped: 17 purge done 08, 18 ensemble/HRP here Later, 19 hyperopt 08, 20 gateway execution here, 21 freeze 09, 22 ranking 09, 23 turbulence 12 step 9, 24 dry-run 11-12, 25 PRIDE later risk report, 26 LOB later intraday.
- Deep dives mapped: vectorbt 08, qlib 08C, freqtrade 08A-B, nautilus 12 step 7-8, finrl 12 step 9, pyportfolioopt here step 4.
- Ledger `inefficiencies-A-J.md` B D F G H J built, E open 08, A built dedupe, C open prompt, I infra built.
- Slices `04:9` A1 rehearsal 12, A2 replace+shock later monitor, A3 ledger+skills+kill+env+allocator loop covered here execution guards.
- 07 seven gaps, 08 1+2+5, 09 top3+3+3, 10 env 18+ paper-days, 11 paper all 6 + 7 stores, 12 seven-day 10, 13 risk full. Chain closed.
