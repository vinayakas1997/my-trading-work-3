---
name: 05-risk-budget
status: Not Started
phase: 3
code: D5
depends_on: [04-daily-plan-document]
unlocks: [07-validation]
---

# Step 05 — Daily Risk Budget + Regime-Tightened Bands

## Why this step

Today there is only one risk limit: Stage 3's circuit breaker halts
everything at -20% drawdown. There is nothing softer — no intraday limit
("if the day is down 5% by noon, stop opening new positions"), no
per-symbol dynamic tightening when regime moves against a position's tag.

From your conversation: the plan should know "what unexpected can happen,
what is the risk measures, it will know when to exit the market with
probability." This step builds the risk measures layer.

## What we're achieving

- A soft daily risk budget: configurable intraday loss limit that triggers
  position-hold (not full kill) when breached.
- Regime-shift dynamic tightening: when regime moves against a strategy's
  tag alignment, its risk bands shrink automatically (smaller position,
  tighter invalidation) rather than just reducing its capital share.
- The approach is informed by research on institutional risk budgeting.

## Where it matters in the future

This is the operational risk layer that sits between the probabilistic exit
(per-position) and the circuit breaker (portfolio kill switch). It gives the
plan graduated responses instead of all-or-nothing.

## How it connects to other steps

- **Depends on Step 04** — needs the unified daily plan document to know
  current positions and their risk status.
- **Unlocks Step 07** — validation needs the full risk picture to be tested.

## Substeps

1. **Research.** Before writing code, search for:
   - "intraday risk budgeting institutional trading"
   - "volatility adjusted position limits"
   - "intraday loss limit vs drawdown limit"
   - "dynamic risk band tightening regime change"
   Document findings. Key questions: what are common intraday loss limits
   (as % of daily VaR or account equity)? How do firms tighten risk bands
   dynamically when regime changes?

2. **Read current risk infrastructure.** Re-read:
   - `vinu_portfolio/circuit_breakers.py` (the existing kill switch).
   - `vinu_portfolio/drawdown_scheduler.py` (monitoring).
   - Stage 3 in `live-safety/SKILL.md` for context.
   - `TradePlan.risk_bands` to see what fields already exist.
   Understand exactly what exists and where the gap is.

3. **Design the daily risk budget.** Define:
   - Metric: % of account equity, or % of daily VaR, or something else.
   - Threshold: when breached, what happens? (Stop opening new positions?
     Reduce all positions by X%? Hold only.)
   - Reset: does the budget reset daily? Or accumulate?
   - Configuration: env vars matching the existing `VINU_PORTFOLIO_*` pattern.

4. **Design the regime-tightening.** For each position where regime moves
   against its tag alignment:
   - What tightens? (Max position size? Invalidation threshold? Both?)
   - By how much? (Fixed multiplier? Scaled by misalignment severity?)
   - Does it trigger an exit or just a reduction?

5. **Implement.** Add the risk budget logic, the regime-tightening logic,
   and integrate both into `compute_daily_allocation()` and/or the
   unified daily plan from Step 04. Write tests.

6. **Update skill docs.** Document in `live-safety/SKILL.md` and
   `daily-allocation/SKILL.md`.

## Research notes

**Approach chosen: Multi-tier risk budget + Dynamic Risk Parity.**

**Tier structure (from institutional practice):**
| Tier | Limit | Action |
|---|---|---|
| Per-trade | 1-2% of capital | Close position via stop |
| Daily soft | -3% MTD | Stop opening new positions; maintain existing |
| Daily hard | -5% MTD | Reduce positions by loss/limit ratio |
| Portfolio | -20% YTD | Full halt (existing circuit breaker) |

**Daily budget formula:**
```
daily_soft_stop = 0.03 * equity   # stop opening
daily_hard_stop = 0.05 * equity   # start reducing
if daily_loss < soft_stop: new_positions_allowed = False
if daily_loss < hard_stop: reduce_factor = min(1.0, loss / hard_stop)
```

**Volatility targeting (position-level):**
```
r_scaled(t) = (σ_target / σ_hat(t)) * r(t)    # σ_target ≈ 12% annualized
```
Key finding: volatility targeting reduces left-tail events across ALL asset
classes, but only improves Sharpe for risk assets (equities/credit).

**Conditional VT (preferred over conventional):**
Only adjust in extreme volatility states (top/bottom tercile). Conventional VT
fails because it rebalances unconditionally. Gains are concentrated in high-vol
states where clustering is strongest (autocorrelation 0.52 vs 0.14 in low-vol).

**Dynamic Risk Parity (replaces static inverse-vol):**
- Update covariance matrix with 60-day rolling window, monthly rebalance
- Study results (2015-2025, 11 assets): DRP 26.86% return vs static RP 25.40%,
  with LOWER max drawdown (-0.277 vs -0.279)
- Your current inverse-vol approach is closest to Volatility Targeting in the
  VT/VP/Pyramiding comparison (40 futures, 1980-2024)

**Regime-tightening formula:**
```
new_max_position = current_limit × alignment_score
alignment_score = 1.0 when regime matches tag → 0.3 when strongly opposing
invalidation_distance = current_distance × alignment_score
```
Shift from trim to exit level when alignment_score < 0.3.

## What was actually built

*(To be filled in after implementation.)*

## Definition of done

- [ ] Research done and documented in this file.
- [ ] Daily risk budget implemented and tested (metric, threshold, action).
- [ ] Regime-tightening logic implemented and tested.
- [ ] Both integrated into the daily allocation/plan pipeline.
- [ ] Tests cover normal operation, budget breach, regime-shift tightening.
- [ ] Skill docs updated.

## Open risks / assumptions

- The daily risk budget concept assumes the system can track intraday P&L.
  Verify that `vinu-live`'s feedback loop or the broker route provides
  enough data to compute "how much have we lost today" — if not, this
  step may need to also build a simple intraday tracker.
- Regime-tightening depends on regime classification being available at
  plan time — Step 10's `classify_current_regime()` does this but it
  runs once per allocation. If intraday regime shifts aren't detectable,
  tightening only applies at the daily planning moment, not mid-day.
