# Portfolio Inside - How It Works + Gaps + Extras + Regimes 4 (2026-09-08)

Simple English. Short sentences. You can read any time.

Folder: `questions -answers/`
This is `19`. Related: `13`, `18`.
Status: Portfolio step closed with 4 gaps + 3 extras + 4 regimes = 11 total. Code steps ready to build next, no code changed yet in this doc.

---

## How portfolio works today (4 goods)

1. Risk parity inverse-vol. File `vinu-portfolio/service.py:232` `allocate_risk_parity`. Lower vol higher weight. No return estimate needed. Robust. Good.
2. Build + corr + composition gaps. File `service.py:288` `build_portfolio`. Returns df shared with corr, weights + `composition_view` gaps Row 4. Good view.
3. Daily allocation regime tilt 0.3 + outcome tilt 0.3 + min 5 entries. Files `service.py:385`, `config.py:53`. Aligned tilts up bounded, mismatch down, low accuracy down. Fail-open on tilt data. Good.
4. Returns cache 60s. File `service.py:53`. J double fetch fixed. Historical sim walk-forward daily rebalance exists. File `historical_simulation.py:94`. Good for test.

---

## 4 gaps in portfolio (inefficiencies)

### 1. Composition view only, no action
File `service.py:347` `_check_composition_gaps` returns view. No auto rebalance on gaps. Example: all 6 same ticker, warning only.
Fix: gap -> rebalance request or cap weight. Small rule. Do first with 2.
Knobs: `VINU_PORTFOLIO_COMPOSITION_ACTION=true`, `VINU_PORTFOLIO_MAX_SYMBOL_PCT=0.20`.
Status: Open.

### 2. Tilt bounds 0.3 provisional + min 5 provisional
File `config.py:53`. Not tuned with live. 0.3 may be big or small. Min 5 may be low.
Fix: tune after 30 trades + live 60d, or Hyperopt tilt bound 0.1 to 0.5. Small tuning. Do first.
Knobs: `VINU_PORTFOLIO_REGIME_TILT_BOUND=0.3`, `VINU_PORTFOLIO_OUTCOME_TILT_BOUND=0.3`, `min_calibration_entries_for_tilt=5` kept.
Status: Open.

### 3. No drawdown de-risk (you liked, DD great)
Portfolio DD -10 percent still full weights. No halve on breach.
Fix: DD over 10 percent halve all, over 15 percent flat to cash. Link breaker `engine.py:25` daily loss to portfolio weights. Small breaker link. Do first with regimes 1-3.
Knobs: `VINU_PORTFOLIO_DD_HALVE_PCT=0.10`, `VINU_PORTFOLIO_DD_FLAT_PCT=0.15`.
Status: Open.

### 4. Mixed horizons one book
1D + 1H strategies same parity pool. 1H trades 24x faster, same weight as 1D. Risk mismatched.
Fix: separate sleeves 1D book + 1H book, or horizon weight scaling by sqrt bars. Small sleeve tag `interval` on artifact. After 1-2 green.
Knobs: `VINU_PORTFOLIO_SLEEVES_ENABLED=false` (false now, true after 1 green), `VINU_PORTFOLIO_HORIZON_SCALING=true`.
Status: Open.

---

## 3 advanced from other repos on top

### 5. PyPortfolioOpt HRP + L2 + BL (Later, same as 13 step 4)
Source `pyportfolioopt-HRP.md:21`. HRP clustering no inversion, L2 gamma 0.1 de-concentrate, BL views. Medium, after 4 guards green `tickers 4 + strategies 18 + trades 30 + live 60`. Same trigger as `13` doc. Decision first, code next.
Knobs: `VINU_ALLOCATOR_HRP_ENABLED`, `VINU_ALLOCATOR_L2_GAMMA`, `VINU_ALLOCATOR_BL_ENABLED` kept from `10,13`.
Status: Later. Saved here never lost.

### 6. cpz-quant NCO + HERC + Schur + CVaR + robust + cardinality
Web `cpz-quant` family table. NCO nested clusters for unstable corr, HERC equal risk per cluster, mean-CVaR tail, box uncertainty robust, max 10 positions cardinality.
Adopt NCO + CVaR first, rest later. Medium. Tail gate same as `13` step 1. `VINU_RISK_CVAR_THRESHOLD` kept.
Status: Later batch. After HRP green.

### 7. wraquant + ML4Trading regime blend + allocator compare
Optimize per regime bull and bear separately, blend by regime prob, not hard switch. Plus compare equal vs inverse-vol vs MVO vs HRP quarterly. Adopt regime blend + quarterly compare notebook. Low.
Where: `historical_simulation.py:94` walk-forward + new `notebooks/allocator_compare.py`.
Status: Open. Low notebook + blend formula. With regimes 2 below.

---

## 4 regimes missed on top (you asked, DD + regimes full)

How regime works today: one SPY 1d for all. File `service.py:393` fetches SPY, classifies bull, bear, sideways, high_vol. Tags per strategy, match `1 + 0.3`, mismatch `1 - 0.3`, high_vol `1.0` neutral. File `service.py:486`. Recompute daily. File `config.py:170`. Per-regime Sharpe in sim + tag on top 3 planned `09`. Good view, not live blend.

### 8. Single SPY regime for all tickers
AAPL bull while SPY sideways possible. NVDA high_vol while AAPL calm possible. One regime mis-tilts others.
Fix: per-symbol regime from own candles + SPY fallback. Small 1 loop. Do now with DD.
Status: Open.

### 9. Hard tilt +-0.3, no probability blend
Today bull 100 or bear 100. Real 60 bull 40 sideways. Web `wraquant regime-adjusted` blends bull and bear portfolios by prob.
Fix: blend weights by regime prob. Avoids flip-flop turnover. Small formula. Do now.
Status: Open.

### 10. High_vol neutral 1.0 wrong
File `service.py:492` high_vol returns 1.0. Highest risk does nothing. Web 2022 flip broke parity AQR -25 percent.
Fix: high_vol de-risks all to half + pauses entries, allows exits. Same as turbulence gate `12` step 9 + DD step 3. Small gate. Do now.
Knobs: `VINU_PORTFOLIO_HIGH_VOL_DE_RISK=true`.
Status: Open.

### 11. No regime covariance + no hysteresis
Same corr all regimes, but corr spikes in crash. No 2-day confirm flips bull bear bull daily, turnover spike.
Fix: regime-conditional corr per bull and bear + 2-day confirm before flip + turnover cap. Medium. `cpz-quant` NCO + `wraquant` covariance pattern. Later after 8-10 green.
Knobs: `VINU_PORTFOLIO_REGIME_COV_ENABLED=false`, `VINU_PORTFOLIO_HYSTERESIS_DAYS=2`, `VINU_PORTFOLIO_TURNOVER_CAP=0.5`.
Status: Later.

---

## Knobs full list for portfolio (add to 10 later build)

- Base kept: `VINU_PORTFOLIO_REGIME_TILT_BOUND`, `VINU_PORTFOLIO_OUTCOME_TILT_BOUND`, `min_calibration_entries_for_tilt`, returns cache 60s.
- Gaps: `VINU_PORTFOLIO_COMPOSITION_ACTION`, `VINU_PORTFOLIO_MAX_SYMBOL_PCT`, `VINU_PORTFOLIO_DD_HALVE_PCT`, `VINU_PORTFOLIO_DD_FLAT_PCT`, `VINU_PORTFOLIO_SLEEVES_ENABLED`, `VINU_PORTFOLIO_HORIZON_SCALING`.
- Advanced: HRP L2 BL kept from `10,13`, `VINU_PORTFOLIO_CVAR` via risk gate, NCO HERC robust cardinality later.
- Regimes: `VINU_PORTFOLIO_PER_SYMBOL_REGIME=true`, `VINU_PORTFOLIO_REGIME_BLEND=true`, `VINU_PORTFOLIO_HIGH_VOL_DE_RISK=true`, `VINU_PORTFOLIO_REGIME_COV_ENABLED`, `VINU_PORTFOLIO_HYSTERESIS_DAYS`, `VINU_PORTFOLIO_TURNOVER_CAP`.
- Future timeframe: same `VINU_SWEEP_INTERVALS` drives sleeves, no extra knob. New interval sleeve appears auto.

---

## Order to build (DD + regimes 1-3 first, closed 11)

1. Composition action + tilt tune. 1-2 together. Small clarity. Do first.
2. DD de-risk + per-symbol regime + prob blend + high_vol de-risk. 3 + 8-10 together. Small safety. You liked DD, regimes you asked. Do first batch with 1.
3. Sleeves + regime covariance + hysteresis. 4 + 11 together. After 1-2 green. Medium.
4. HRP L2 BL + NCO CVaR + blend compare notebook. 5-7 together. After 3 green. Needs 4 guards + live 60d.
5. Test: composition caps overweight, tilt tunes after 30 trades, DD halves at 10 flats at 15, per-symbol differs from SPY, blend no flip-flop, high_vol halves, corr per regime, hysteresis 2-day confirm, turnover capped.

After 1-5, portfolio done. Next is 6 learning over time. Different doc.

---
Link: Learning over time 4 gaps + 3 extras + talk diagram is in `20-learning-over-time.md`. 19 -> 20 = portfolio -> learning closed. Full pipeline 0-9 + learning chain closed.

---

## All covered proof (nothing missed for portfolio + regimes)

- Engine `service.py:232` parity, `288` build, `347` composition, `385` daily tilt, `393` SPY regime, `486` alignment, `505` allocation, `53` cache, `config.py:53` bounds. All read.
- Gaps mapped: composition Row 4, tilt Row 7 provisional `07-caps-decision`, DD breaker link, sleeves horizon mismatch.
- Repos mapped: PyPortfolioOpt HRP L2 BL 5 here, cpz-quant NCO HERC CVaR 6 here, wraquant ML4Trading blend compare 7 here. Qlib purge done 08, Freqtrade pairlist done 08/18, Nautilus fills done 12/16, FinRL turbulence done 12, Lean cycle done 15. No new repo needed.
- Decisions `05-sizing` Kelly parity tilts kept, `07-caps` K3 iters5 holdout20 kept, `08-calibration` min entries kept.
- Ledger `inefficiencies-A-J.md` J cache built, H ref_id, F retry, B parallelism, D cache kept. E open 08.
- 09 top3 regime tag, 10 knobs, 11 paper all 6, 12 seven-day 10, 13 risk full 4-guard, 14 storage full, 15 monitor closed, 16 broker closed, 17 UI closed, 18 data closed kept. 19 closes portfolio + regimes.
