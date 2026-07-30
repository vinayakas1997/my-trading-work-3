---
name: research-findings
status: living-document
purpose: compiled web research for steps that require external knowledge before implementation
---

# Research Findings — Pre-Live Readiness Plan

This file documents every web research finding organized by the step it applies to.
Each section covers methods, formulas, key numbers, Python libraries, and sources.

---

## Step 02 — Shock Clustering (Multi-Symbol Correlation)

### The Problem

`shock_clustering` currently returns `"single_symbol"` because `AngleRunner`
feeds one symbol at a time. The correlation matrix in `build_portfolio()` uses
calm-day co-movement only, which **understates portfolio tail risk by up to
2.2× in crisis periods** (proven by controlled DCC-GARCH studies).

### Recommended Approach: DCC-GARCH (Dynamic Conditional Correlation)

**Why DCC-GARCH over alternatives:**

| Model | Pros | Cons |
|---|---|---|
| **DCC-GARCH** (Engle 2002) | Time-varying correlations, 2-step estimation (parallelizable), scales to d=50 assets (152 params vs 3.25M for full MGARCH) | Requires return history; slightly more complex to implement |
| Rolling window | Simple, no assumptions | No single window is best overall AND in crisis; lags at regime boundaries |
| EWMA | Adaptive, simple | Fixed decay factor; no volatility clustering model |
| HMM correlation | Regime-aware, interpretable | Harder to implement; needs regime label stability |
| Static (full sample) | Simplest | **Dangerous** — looks well-calibrated on average (breach rate 0.049) while crisis breach rate is 2.2× nominal |

**The evidence:** In controlled studies (synthetic data with known calm→crisis→recovery
correlation path from 0.3→0.9→0.5):

| Estimator | MAE overall | MAE crisis | VaR breach (crisis) |
|---|---|---|---|
| Static full-sample | 0.238 | 0.208 | 0.111 (2.2× nominal) |
| Rolling w=60 | 0.069 | 0.031 | 0.069 |
| **DCC-GARCH** | **0.061** | **0.028** | **0.063** |
| True covariance | — | — | 0.060 |

DCC tracks the correlation path with **7× lower crisis error** than static,
and reduces hedged-spread variance by **20.8% inside the crisis**.

### How DCC-GARCH Works (2-Step Estimation)

**Step 1:** Fit univariate GARCH(1,1) for each asset `i`:

```
r_{i,t} = μ_i + ε_{i,t}
σ²_{i,t} = ω_i + α_i ε²_{i,t-1} + β_i σ²_{i,t-1}
z_{i,t} = ε_{i,t} / σ_{i,t}
```

**Step 2:** Estimate DCC parameters on standardized residuals:

```
Q_t = (1 - a - b) * Q̄ + a * z_{t-1} * z'_{t-1} + b * Q_{t-1}
R_t = diag(Q_t)^{-1/2} * Q_t * diag(Q_t)^{-1/2}
```

Where:
- `Q̄` = unconditional correlation of standardized residuals
- `a` = news impact parameter (typical: 0.01–0.05)
- `b` = persistence parameter (typical: 0.90–0.97)
- `R_t` = time-varying correlation matrix at time `t`

### Practical Implementation for Your Codebase

**Python libraries available:**
- `arch` — univariate GARCH estimation (already in your ecosystem)
- Custom DCC layer on top of `arch`'s standardized residuals (~100 lines)
- Alternative: `hmmlearn` for regime-switching correlation approach

**Recommendation for Step 02:**

Build a lightweight DCC estimator in `vinu-portfolio` (or `vinu-initial-analysis`)
that:
1. Fits univariate GARCH(1,1) via `arch` for each portfolio symbol
2. Computes time-varying correlation matrix once per daily allocation run
3. Stores the current crisis/normal correlation estimate separately from the
   calm-day estimate used by `build_portfolio()`
4. Feeds shock correlation delta into the daily plan readiness score

This is **not** a full MGARCH implementation — it's a pragmatic ~100-200 line
Python module that improves on "1 symbol" without adding a PhD project.

**Key numbers to implement:**
- DCC parameters: `a ≈ 0.03, b ≈ 0.95` (literature defaults, re-estimateable)
- Crisis correlation warning threshold: correlation delta > 0.4 vs calm baseline
- Portfolio shock count: number of positions with pairwise crisis correlation > 0.7

### Key Sources

- Engle (2002) — "Dynamic Conditional Correlation: A Simple Class of Multivariate
  Generalized Autoregressive Conditional Heteroskedasticity Models"
- DCC-GARCH controlled study (2025): dcc-correlation.marketmaker.cc — synthetic
  data calibration, shows 7× better crisis tracking vs static, 2.2× VaR understatement
- Mighri & Mansouri (2013) — DCC analysis of 2007-2010 crisis; correlations
  rose from 0.26→0.56 (HK-China), 0.03→0.38 (HK-US)
- Python implementation reference: github.com/kniyer/correlation-models
  (DCC-GARCH + Copula + HMM comparison, MIT license)

---

## Step 03 — Probabilistic Exit Model

### The Problem

Current exits are deterministic threshold crossings (`invalidation_conditions`).
Your vision requires probability-scored exits ("probability of adverse move
now exceeds X%") and confidence decay over time.

### Kelly Criterion (Foundation)

**Full Kelly formula:**

```
f* = (b * p - q) / b
```

Where:
- `f*` = optimal fraction of capital to risk
- `p` = probability of winning
- `q` = 1 - p = probability of losing
- `b` = net odds received on win (e.g., 1:1 → b=1)

**Modified Kelly (for trading, where b = avg_win / avg_loss):**

```
f* = W - [(1 - W) / R]
```

Where:
- `W` = win rate (e.g., 0.55)
- `R` = average win / average loss

**Example:** Win rate 55%, even-money payoff (R=1):
```
f* = 0.55 - (0.45 / 1.0) = 0.10 → 10% of capital
```

### Fractional Kelly (The Industry Standard)

**Critical finding:** Full Kelly is mathematically optimal but produces brutally
volatile equity curves (50% drawdowns are common). Professional consensus:

- **Half-Kelly** (0.25-0.5 of full Kelly) is the standard
- Academic papers show half-Kelly is a Bayes estimator under realistic priors
- Modified Kelly with Beta(50,50) prior produces exactly half-Kelly results

**Why half-Kelly:** Small overestimates of win probability `p` produce large
over-bets that compound badly. Half-Kelly sacrifices ~25% of growth for ~50%
less drawdown variance.

### Risk-Constrained Kelly (RCK)

For drawdown-aware position sizing:

```
maximize  E[log(r^T * b)]
subject to:
  sum(b) = 1, b >= 0
  E[(r^T * b)^(-λ)] <= 1
```

Where `λ = log(β) / log(α)` and:
- `α` = drawdown threshold (e.g., 0.7 = 30% drawdown)
- `β` = maximum acceptable probability of hitting that drawdown (e.g., 0.1 = 10%)

**This is the formula for your governor's expectancy heuristic.**
RCK bets guarantee the drawdown probability constraint is met.

### Stop-Loss Probability Bands (From Research)

Based on multiple studies and professional practice:

| Band | Probability of Thesis Failure | Action |
|---|---|---|
| Watch | < 30% | No action; monitor normally |
| Trim | 30-40% | Reduce position by 50% |
| Exit | 40-50% | Reduce to 25% or flat |
| Hard Exit | 60-70% | Full exit immediately |

**Professional trader norms:**
- Never risk > 1-2% of capital on a single trade
- Never have > 20-30% of capital exposed across all trades at once
- ATR-based stops: 2-3× ATR multiplier
- Trail distance: 8-12¢ normal vol, 5-8¢ high vol (prediction market data)

### Confidence Decay Model

**Linear decay over forecast horizon:**

```
confidence(t) = initial_confidence * max(0, (horizon_days - t) / horizon_days)
```

**Exponential decay (preferred):**

```
confidence(t) = initial_confidence * exp(-λ * t)
```

Where `λ = -ln(0.5) / half_life` and `half_life = horizon_days / 3` (decay to
~5% of original at horizon).

**Combined probability of thesis failure:**

```
P_failure(t) = (1 - calibration_accuracy) * w_cal + P_price_against * w_price + (1 - confidence(t)) * w_time
```

Where weights sum to 1 and can be set empirically:
- `w_cal = 0.4` (calibration track record)
- `w_price = 0.4` (distance from forecast / magnitude_std)
- `w_time = 0.2` (staleness)

**When price crosses forecast ± 1 magnitude_std:** weight shifts to price.
**When confidence decays below 0.3:** time component triggers trim.
**When confidence decays below 0.1:** time component triggers exit.

### Key Sources

- Kelly (1956) — "A New Interpretation of Information Rate" (original paper)
- Nielsen — "The Kelly Growth Optimal Strategy with a Stop-Loss Rule"
  (hedge fund context: soft/hard stops, VaR limits, period-reset stops)
- Busseti, Ryu, Boyd (2016) — "Risk-Constrained Kelly Gambling" (convex
  optimization for drawdown-aware sizing, RCK formula above)
- Modified Kelly Criteria (SFU) — proves half-Kelly is Bayes estimator under
  Beta(50,50) prior; theoretical rationale for fractional Kelly
- Thrive Research (2025) — AI stop-loss optimization: 0.25-0.5 Kelly, ATR-based
  stops, portfolio-level risk monitoring

---

## Step 05 — Daily Risk Budget & Dynamic Bands

### The Problem

Today only one risk limit exists: the -20% drawdown circuit breaker (all-or-nothing).
Your vision requires graduated responses: "down 5% by noon → stop opening but
don't kill existing positions," plus dynamic tightening when regime shifts.

### Institutional Risk Budgeting Structure

Professional trading desks use a multi-tier structure:

| Tier | Limit | Trigger | Action |
|---|---|---|---|
| **Per-trade** | 1-2% of capital | Stop-loss hit | Close position |
| **Daily soft** | 3-5% MTD loss | Breach | Stop opening new positions; reduce VaR limit by 50% |
| **Daily hard** | 8-10% MTD loss | Breach | Reduce all positions to 25%; VaR to 0 |
| **Portfolio** | 15-20% YTD drawdown | Breach | Full halt (your existing circuit breaker) |

### Volatility Targeting Framework

**Volatility-scaled returns:**

```
r_vol_targeted(t) = (σ_target / σ_hat(t)) * r(t)
```

Where:
- `σ_target` = target volatility (e.g., 12% annualized)
- `σ_hat(t)` = estimated conditional volatility from rolling window

**Key empirical finding:** Volatility targeting improves Sharpe ratios for risk
assets (equities, credit) but not for bonds/currencies/commodities. However, it
**reduces left-tail events across ALL asset classes** — the most important
benefit.

**Conditional Volatility Targeting (newer, better approach):**

Only adjust risk exposure in extreme volatility states:

```
r_conditional(t) = r(t) * (1 + I(t) * (σ_target / σ_hat(t) - 1))
```

Where `I(t)` = 1 when volatility is in top/bottom tercile, 0 otherwise.

Why this matters: conventional volatility targeting fails because it rebalances
unconditionally. The gains are concentrated in high-volatility states (where
volatility clustering is strongest: autocorrelation 0.52 in high-vol vs 0.14 in
low-vol). Conditional targeting reduces max drawdowns, turnover, and leverage.

### Dynamic Risk Parity (DRP)

**Current approach:** Static risk-parity (inverse-vol) using full-sample covariance.
**Better approach:** Rolling-window risk parity updating covariance monthly.

Results from empirical study (2015-2025, 11 assets):

| Strategy | Return | Volatility | Sharpe | Max Drawdown |
|---|---|---|---|---|
| Static Risk Parity | 25.40% | 0.186 | 1.368 | -0.279 |
| **Dynamic RP** (monthly rolling) | **26.86%** | **0.190** | **1.418** | **-0.277** |
| Markowitz MVO | 25.86% | 0.156 | 1.655 | -0.312 |

DRP achieves the highest return **and** lowest max drawdown simultaneously
— the adaptive covariance update captures regime shifts while static RP misses them.

### Regime-Tightened Risk Bands

When regime moves against a strategy's tag alignment:

1. **Tighten max position size:** Multiply current position limit by
   `alignment_score` (e.g., regime trends against tag → alignment = 0.6 → position
   shrinks to 60%)
2. **Tighten invalidation threshold:** Move exit trigger closer by
   `(1 - alignment_score) * current_distance`
3. **Shift from trim to exit bands:** If alignment < 0.3 escalate the
   probabilistic exit band actions

### Position Sizing Comparison (Trend Following)

Three frameworks tested on 40 futures markets (1980-2024):

| Method | Annual Return | MDD | Sharpe |
|---|---|---|---|
| **Volatility Targeting** | 11.46% | -25.65% | Best risk control |
| **Volatility Parity** | 12.83% | -25.8% | Balanced |
| **Vol Parity + Pyramiding** | 20.00% | -48.69% | Highest return, highest risk |

Key insight: **VT is for stability, VP is for moderate growth, pyramiding is
for fat-tail capture.** Your current inverse-vol approach is closest to VT/VP.

### Recommended Daily Budget Formula

```
daily_loss_limit = -5% × account_equity
daily_soft_stop = -3% × account_equity  # stop opening, maintain positions
daily_loss_today = current_day_P&L - previous_day_close_P&L

if daily_loss_today < daily_soft_stop:
    new_positions_allowed = False
    existing_positions_keep = True

if daily_loss_today < daily_loss_limit:
    reduce_all_positions_by = min(1.0, abs(daily_loss_today / daily_loss_limit))
    # E.g., at -4% loss → 4/5 = 80% kept; at -5% → 0% kept
```

### Key Sources

- Moreira & Muir (2017) — "Volatility Managed Portfolios" — scaling by inverse
  variance improves Sharpe for market, value, momentum factors
- Harvey et al. (2018) — "The Impact of Volatility Targeting" across 60+ assets;
  reduces left-tail events universally
- Bongaerts, Kang, van Dijk (2020) — "Conditional Volatility Targeting"
  — conventional VT fails; conditional on volatility states works
- Dynamic Risk Parity study (2026, MDPI) — DRP beats static RP and Markowitz
  on return and max drawdown simultaneously
- Concretum Group (2024) — VT vs VP vs Pyramiding comparison, 40 futures, 1980-2024
- Nielsen — "Kelly with Stop-Loss Rule" — multi-tier stop structure

---

## Supplementary — Regime Detection (Feeds Steps 02, 04, 05)

### Hidden Markov Model (HMM) for Regime Detection

**Standard approach:** Gaussian HMM on log returns + 20-day rolling volatility.

```
X = [log_returns, rolling_vol_20d]
model = GaussianHMM(n_components=3, covariance_type='full')
model.fit(X)
states = model.predict(X)
probs = model.predict_proba(X)
```

**Number of states:**
- 2 states: Risk-on/risk-off (binary)
- **3 states: Sweet spot** — bull/bear/range; maps to your tags.yaml vocabulary
- 4 states: Differentiates low-vol trend vs low-vol range

**Labeling states (post-hoc):**
Sort by mean return: highest = bull, lowest = bear, middle = range/transition.

**Transition matrix persistence:** Diagonal values > 0.90 mean regimes are
stable (good for trading); < 0.70 means noisy or overfit.

**Walk-forward fitting (critical):**
Never fit on full dataset — that introduces look-ahead bias. Re-fit on a rolling
5-year window every 21 trading days.

### Ensemble HMM (Production Approach)

Run multiple HMMs with different feature sets and combine via probability averaging:

```
feature_sets = [
    ['log_returns', 'realized_vol', 'vix'],
    ['log_returns', 'realized_vol', 'momentum_20d'],
    ['log_returns', 'vix', 'vol_of_vol'],
]
```

Each model votes on "favorable probability"; ensemble average is the final signal.

### Comparison: HMM vs Your Current Approach

| Aspect | Current (21-day vol + 0.7 quantile) | HMM (3-state) |
|---|---|---|
| State granularity | 4 labels (bull/bear/high_vol/sideways) | 3 states + probabilities |
| Volatility source | 21-day rolling | GARCH or rolling |
| Look-ahead bias | None (point-in-time) | Must use walk-forward |
| Probabilistic output | Hard label | Soft probability per state |
| Adaptability | Fixed threshold | Re-estimates from data |
| Implementation | ~50 lines | ~100 lines + hmmlearn |

**Recommendation:** Keep your current approach as the primary (it's simpler and
already tested). Add a supplementary HMM that feeds into the readiness score
("HMM regime confidence") so the plan can say "regime classification is
high-confidence" vs "uncertain."

### Key Sources

- Python & Trading (2026) — HMM with buy/hold; halved max drawdown vs buy-hold
- RegimeForecast (2026) — comprehensive HMM guide: ensemble methods, walk-forward,
  BIC model selection, multi-start optimization
- QuantBrains (2026) — complete pipeline: fetch → train → decode → label → strategy
- QuantInsti (2025) — HMM + Random Forest regime-adaptive strategy; Sharpe 1.76
  vs 1.16 buy-hold, max drawdown -20% vs -28%

---

## Supplementary — Agent Orchestration (Step 06)

### Architectures (from Anthropic's Production Guide)

| Pattern | Structure | When to Use |
|---|---|---|
| **Prompt chaining** | Sequential LLM calls, each processes previous output | Predictable, linear tasks |
| **Routing** | Classify input → specialized handler | Different inputs need different paths |
| **Parallelization** | Multiple LLMs run simultaneously, outputs aggregated | Independent subtasks |
| **Orchestrator-workers** | Central LLM delegates to workers, synthesizes | Complex tasks with unknown subtask count |
| **Evaluator-optimizer** | One generates, another evaluates in a loop | Iterative refinement |
| **ReAct agent** | Thought → Action → Observation loop, self-directed | Open-ended tasks with tool use |

### For Your System

The ReAct pattern is the closest match to what you're building. Key design
principles from the research:

1. **Skills as composable knowledge, not scripts** — your existing philosophy
   is exactly right. Each skill is a file the agent reads to understand what
   exists and what it means.

2. **Pre-load summaries, full text on demand** — Option C from Step 06's
   substeps is the right approach. Inject skill summaries in the system prompt,
   provide a `read_skill(name)` tool for full text. This respects the 128k
   context limit.

3. **Tool documentation (ACI) is as important as prompts** — Anthropic found
   they spent more time optimizing tools than prompts for SWE-bench (81%
   resolution rate). Your `vinu-tools-catalog` is exactly this.

4. **Governor at the loop level** — hard limits (max iterations, wall-clock)
   enforced by the loop, heuristics exposed as tool calls the agent can query.
   Your three-part governor (hard + progress + expectancy) maps cleanly onto
   this: hard limits in the loop, heuristics as tools.

5. **Multi-agent patterns exist but start simple** — agent-swarm architectures
   (LangGraph, CrewAI) are available for when you need parallel specialist
   agents. Your swarm system (`vinu_agent/swarm/`) may become useful for Focus
   2 (11 angles in parallel) after the basic ReAct loop works with skills.

### Key Sources

- Anthropic (2024) — "Building Effective AI Agents" — the definitive production
  guide: workflow vs agent distinction, patterns, tool design principles
- LangGraph multi-agent trading systems (multiple GitHub repos 2025-2026):
  parallel agents for technical analysis, sentiment, order flow, risk management
- ReAct Modular Agent for Financial Workflows (2025) — hierarchical
  Planner→Dispatcher→Synthesizer architecture with parallel tool execution

---

## Summary: Key Formulas Cheat Sheet

### Step 02 — DCC Correlation

```
Q_t = (1-a-b)*Q̄ + a*z_{t-1}*z'_{t-1} + b*Q_{t-1}
R_t = diag(Q_t)^(-0.5) * Q_t * diag(Q_t)^(-0.5)
a ≈ 0.03, b ≈ 0.95
```

### Step 03 — Probabilistic Exit

```
f*_kelly = (b*p - q) / b          (Full Kelly)
f*_modified = W - (1-W)/R         (Modified Kelly)
f*_used = 0.25 * f*_kelly         (Quarter-Kelly = safe default)
P_failure(t) = 0.4*cal + 0.4*price + 0.2*time_decay
confidence(t) = initial * exp(-λ*t), λ = ln(2) / (horizon/3)
```

### Step 05 — Risk Budget

```
daily_soft_stop = 0.03 * equity    # Stop opening new positions
daily_hard_stop = 0.05 * equity    # Start reducing positions
r_scaled(t) = (σ_target / σ_hat(t)) * r(t)    # Vol targeting
reduce_factor = min(1.0, loss / daily_hard_stop)  # Gradual reduction
```

### Regime Detection (Supplementary)

```
X = [log_returns, rolling_vol_20d]
P(state|X) = predict_proba(X) via HMM
regime = argmax(mean_return_per_state)  # bull = highest mean
transmat_persistence = diag(transition_matrix)  # >0.90 = good
```
