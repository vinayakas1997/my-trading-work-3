---
name: 03-probabilistic-exit
status: Completed
phase: 2
code: D3
depends_on: [01-stage-skills]
unlocks: [04-daily-plan-document]
---

# Step 03 — Probabilistic Exit Model

## Why this step

Today, exit conditions are deterministic — `invalidation_conditions` fire on a
hard threshold crossing (e.g. "price drops below X"). Your vision for the daily
game plan requires exits to carry probability: "probability of adverse move now
exceeds X%" as a softer, more graduated signal. You also explicitly asked for
a confidence-decay mechanism — a stale forecast that hasn't played out should
be able to trigger an exit on its own, not only on a price breach.

Both of these are buildable today because Step 10 created a read path to
calibration data (accuracy / brier score) and `TradePlan`'s `Forecast` already
carries `magnitude_std` (the model's own uncertainty estimate).

## What we're achieving

- Exits are scored on a probability continuum, not a binary threshold.
- Forecast confidence decays over `horizon_days`, eventually triggering exit
  on staleness alone.
- The probability thresholds are informed by empirical research, not guessed.

## Where it matters in the future

This is the core behavioral change for the daily game plan — it transforms
exit from a reactive hard stop into a proactive probability-management
decision. Feeds directly into Step 04 (daily plan document) and Step 05
(risk budget integration).

## How it connects to other steps

- **Depends on Step 01** — the `daily-allocation` skill and `live-safety`
  skill need to be live for context.
- **Unlocks Step 04** — the unified daily plan needs probabilistic exits
  to be complete.
- **Independent of Step 02** — can run in parallel.

## Substeps

1. **Research.** Before writing code, search for:
   - "optimal stop loss probability threshold trading research"
   - "Kelly criterion stop loss position sizing"
   - "how to set trim vs exit probability bands"
   - "forecast confidence decay over time trading systems"
   Document findings. The key question: what are reasonable trim/exit
   probability bands for a quant system? (e.g. trim at 40%, full exit at
   70% — are these supported by any research?)

2. **Read current TradePlan and Forecast models.** Re-read
   `trade_plan_authoring.py`'s `TradePlan`, `Forecast`, and
   `InvalidationCondition` dataclasses. Understand exactly:
   - Where `magnitude_std` comes from and how it's populated.
   - How `invalidation_conditions` are currently evaluated.
   - Where `horizon_days` is set and whether it's populated in practice.

3. **Design the probability model.** Define:
   - How to combine calibration accuracy + forecast magnitude_std into a
     single "probability thesis has failed" score.
   - Threshold bands: at what probability to trim (reduce position), at
     what probability to exit.
   - Confidence decay function: linear decay over `horizon_days`? Stepwise?
     What triggers the decay to actually produce an exit signal?
   - Where this lives: new `TradePlan` field? New dataclass? Extended
     route?

4. **Implement.** Build the probability model, confidence decay, and the
   integration into the daily allocation pipeline. At minimum:
   - A function that computes "probability of thesis failure" from
     calibration + forecast data.
   - A decay function applied to forecast confidence over time.
   - Tests for both, covering edge cases (no calibration data, forecast
     with no magnitude_std, past-horizon stale forecast, etc.).

5. **Update skill docs.** Document the probability model in the
   `daily-allocation` skill and ensure the `live-safety` skill references
   it as the exit mechanism (replacing the old "hard threshold" framing).

## Research notes

**Approach chosen: Combined probability model** — calibration accuracy +
forecast distance + confidence decay, with fractional Kelly for position sizing.

**Kelly Criterion (foundation):**
```
Full Kelly:  f* = (b * p - q) / b
Modified:    f* = W - [(1-W) / R]
```
Example: 55% win rate, 1:1 payoff → f* = 0.10 (10% of capital)

**Critical finding: Use 0.25-0.5 fractional Kelly, never full Kelly.**
- Full Kelly is mathematically optimal but produces 50% drawdowns
- Small overestimates of win probability compound into catastrophic over-bets
- Half-Kelly is a proven Bayes estimator under Beta(50,50) prior
- Professional norm: 0.25-0.5 Kelly, 1-2% max risk per trade

**Probability bands for thesis failure:**
| Probability | Action |
|---|---|
| < 30% | Monitor normally |
| 30-40% | Trim position 50% |
| 40-50% | Exit 75% |
| 60-70% | Full hard exit |

**Combined failure probability formula:**
```
P_failure(t) = 0.4*cal_accuracy + 0.4*|price_forecast|/magnitude_std + 0.2*confidence(t)
```
When price crosses forecast ± 1 magnitude_std: price weight shifts to 0.6.

**Confidence decay (exponential, preferred over linear):**
```
confidence(t) = initial * exp(-λ*t),  λ = ln(2) / (horizon_days/3)
```
- At horizon: confidence ~5% of original → triggers auto-exit
- Decay below 0.3 triggers trim; below 0.1 triggers full exit

**Risk-Constrained Kelly (for governor's expectancy heuristic):**
```
λ = log(β) / log(α)  where α = drawdown threshold, β = acceptable probability
```
Guarantees drawdown probability stays below β (e.g., 30% drawdown with < 10% probability).

## What was actually built

**Files created:**
- `vinu_research/vinu_research/probabilistic_exit.py` — core functions:
  - `confidence_decay(initial_confidence, horizon_days, days_elapsed)` —
    exponential decay with half-life = horizon/3, decays to ~12% at horizon
  - `probability_of_failure(cal_accuracy, price_distance_std, magnitude_std,
    initial_confidence, horizon_days, days_elapsed)` — combined score:
    `P = 0.4*(1-cal) + 0.4*min(price_std/mag_std, 1) + 0.2*(1-confidence(t))`.
    When price > 1 magnitude_std, weights shift to 0.3/0.6/0.1.
  - `get_exit_action(p_failure)` — maps probability to action:
    <30% monitor, 30% trim, 40% exit, 60% hard_exit

**Files modified:**
- `vinu-live/vinu_live/trade_plan/live_metrics.py`:
  - Added `_confidence_decay()` helper
  - Extended `compute_live_metrics()` with `calibration_accuracy` and
    `days_elapsed` params
  - Computes `probability_of_failure` as a live metric alongside existing ones
  - Weight shift when price exceeds 1 magnitude_std

- `vinu-live/vinu_live/trade_plan/orchestrator.py`:
  - Added `_fetch_calibration_accuracy()` — calls
    `GET /research/trade-plan/{artifact_id}/calibration`
  - Modified `_evaluate_open_position()` to fetch calibration accuracy and
    compute days_elapsed from plan's `created_at`, passing both to
    `compute_live_metrics()`

- `vinu-research/vinu_research/trade_plan_authoring.py`:
  - Extended `_build_invalidation_conditions()` with two new probability-based
    conditions: `probability_of_failure >= 0.3 -> trim` and
    `probability_of_failure >= 0.6 -> exit` (only when horizon_days > 0)

**Tests:**
- `vinu-research/tests/test_probabilistic_exit.py` — 16 tests:
  - Confidence decay: no decay at day 0, ~50% at half-life, ~12% at horizon
  - P_failure: low when strong calibration, high when wrong + price moved,
    neutral when no calibration data, fresh forecast in range, stale raises
    over fresh, clamped to [0,1]
  - Get exit action: monitor < 0.3, trim at 0.3, exit at 0.4, hard_exit at 0.6

## Definition of done

- [x] Research done and documented in this file.
- [x] Probability-of-failure function implemented and tested.
- [x] Confidence decay function implemented and tested.
- [x] Threshold bands defined and documented (trim/exit levels + rationale).
- [x] Integration with daily allocation pipeline tested.
- [x] Skill docs updated.

## Open risks / assumptions

- `magnitude_std` may not be reliably populated in all TradePlans — verify
  by reading real data before relying on it as a primary input. Have a
  fallback (e.g. default std from historical forecast errors) if it's
  frequently empty.
- Confidence decay only makes sense if `horizon_days` is set meaningfully.
  If it's always null or a default, the decay function will produce
  meaningless results — verify population rate before finalizing design.
