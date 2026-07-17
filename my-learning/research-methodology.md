# Research Methodology for Trading Strategy Development

> How to think about alpha, strategy analysis, validation, and refinement.
> A practical framework for systematic research.

---

## 1. Alpha Parameters — What Are We Actually Measuring?

The 619 alpha factors (101 + 158 + 360) are each a **mathematical hypothesis** of the form:

```
ALPHA101_001 = Rank($close, 20) - 0.5
              ↑ hypothesis about mean reversion in 20-day ranks

KMID = (close - open) / (high - low)
       ↑ hypothesis that intraday body/range ratio signals something
```

### What we can extract from each factor

| Information | How | Example |
|------------|-----|---------|
| **Formula** | Read the expression directly | `Corr(open, volume, 10)` |
| **Theme** | Classified in metadata | momentum, reversal, volatility, value |
| **Columns needed** | What data it requires | close, open, high, low, volume, vwap |
| **Decay horizon** | How long the signal lasts | 1 day, 5 days, 20 days |
| **Universe** | Which stocks it applies to | all, large_cap, equity_cn |
| **Warmup** | How many bars needed to compute | 60 bars typically |

### What we CANNOT extract without running them

- Whether the formula actually works on **our specific tickers** (need to compute IC vs forward returns)
- The **optimal parameter** (e.g., `Mean($close, 5)` — is 5 the best window, or should it be 8?)
- **Interaction effects** (factor A + factor B together may be worse than either alone)

### Research approach to alpha factors

```
Step 1: Compute each factor on real data
Step 2: Compute Information Coefficient (IC) vs next-day return
Step 3: Rank factors by IC → find top 10-20
Step 4: Check correlation between top factors → avoid redundant signals
Step 5: Test combined: does the ensemble outperform the best single factor?
```

---

## 2. Strategy Analysis — What Degree Can We Reach?

When a YAML strategy comes in, the current system can tell you:

| Analysis | Tool | What It Tells You |
|----------|------|-------------------|
| Signal values | `GET /candles?indicators=sma_20,rsi_14` | Raw indicator levels |
| Rule trace | `POST /strategies/{name}/evaluate?trace=true` | Which rules fired, which didn't, why |
| Weights | Same endpoint | Portfolio allocation per ticker |
| Backtest metrics | `POST /simulate` or `/simulate/custom` | Sharpe, DD, CAGR, win rate (44+) |
| Monte Carlo validation | Angle 11 | Is the Sharpe real or luck? |
| Walk-forward | Angle 11 | Is performance consistent across time? |
| Deflated Sharpe | Angle 22 | Adjust for multiple testing |
| Drawdown analysis | `GET /correlation/drawdown/{ticker}` | How bad can it get? |
| Regime conditioning | Angle 09 | Does strategy work in bull/bear/both? |

### What's missing for complete strategy analysis

| Missing | Why It Matters |
|---------|---------------|
| Session-aware backtest | Does strategy work in premarket vs regular hours? |
| News-conditioned performance | Does strategy work better on high-news days? |
| Sensitivity analysis | If you change ADX threshold from 25 to 20, does Sharpe change by 0.01 or 0.5? |
| Rolling out-of-sample | Fixed 80/20 split is weak — walk-forward is better but not integrated |
| Monte Carlo integrated in pipeline | Currently manual script, not part of strategy evaluation |

---

## 3. The Validation → Indicator → Refine Loop

```
         ┌─────────────────────────────┐
         │  1. Backtest strategy        │
         │     Get Sharpe = 0.4         │
         └─────────────┬───────────────┘
                       ▼
         ┌─────────────────────────────┐
         │  2. Monte Carlo validation  │
         │     p-value = 0.35          │
         │     → NOT significant       │
         └─────────────┬───────────────┘
                       ▼
         ┌─────────────────────────────┐
         │  3. Cross-validate          │
         │  - Walk-forward (gap=0.56)  │
         │  - News-conditioned         │
         │  - Regime-conditioned       │
         └─────────────┬───────────────┘
                       ▼
         ┌─────────────────────────────┐
         │  4. Indicator drill-down    │
         │  "ADX=25 threshold: optimal?"│
         │  "RSI range matters more?"  │
         └─────────────┬───────────────┘
                       ▼
         ┌─────────────────────────────┐
         │  5. Refine                  │
         │  Change ADX: 25 → 20        │
         │  Go back to step 1          │
         └─────────────────────────────┘
```

### Key research principle

> **Change ONE thing at a time.**

If you change ADX threshold AND RSI period AND add a news filter in one step, you won't know which change caused the improvement (or degradation).

---

## 4. How to Think as a Researcher

### The core mental model

> **"Every strategy is a hypothesis."**

```
Hypothesis: "When SMA9 crosses above SMA21 AND ADX > 25, prices tend to rise"

Test 1: Compute the signal → does it predict forward returns?
   ↓ No → reject hypothesis, try something else
   ↓ Yes → proceed

Test 2: Monte Carlo permutation → is the prediction real or random?
   ↓ p > 0.05 → likely random, reject
   ↓ p < 0.05 → proceed cautiously

Test 3: Walk-forward → does it work in all time periods?
   ↓ gap > 0.5 → inconsistent, refine or reject
   ↓ gap < 0.3 → consistent, proceed

Test 4: News-condition → does news amplify or reduce the signal?
   ↓ Signal only works on high-news days → you found a news-alpha connection
   ↓ Signal works regardless → robust but no news edge

Test 5: Refine → change one parameter, re-run tests 1-4
   ↓ Improved → keep the change
   ↓ Degraded → revert
```

### The three golden rules

1. **Signal before strategy**: Don't design a complex rule system until you've confirmed a baseline alpha exists. If `close > SMA20` doesn't predict anything, adding ADX+RSI+volume filters won't create a signal — it'll just overfit to noise.

2. **Validate before you optimize**: Monte Carlo p-value is your gatekeeper. If p > 0.05, stop. Don't tune parameters on a random signal — you'll optimize for luck, not skill.

3. **One variable per iteration**: Change ADX threshold → re-validate. Change RSI threshold → re-validate. Change both at once → you don't know what worked.

---

## 5. Decision Framework

| If Monte Carlo says... | And Walk-forward says... | Your action |
|------------------------|-------------------------|-------------|
| p < 0.05 (real) | gap < 0.3 (consistent) | ✅ Strategy is viable. Deploy with confidence. |
| p < 0.05 (real) | gap > 0.5 (inconsistent) | ⚠️ Strategy has signal but fragile. Needs regime filter. |
| p > 0.05 (luck) | any | ❌ Stop. No amount of tuning will fix this. New hypothesis needed. |
| p < 0.05 (real) | gap < 0.3 | 🔍 Now test news-conditioned. Does news amplify the signal? |

---

## 6. The Complete Research Pipeline

```
                          ┌───────────────────────┐
                          │  Raw Data              │
                          │  (OHLCV + News)        │
                          └──────────┬────────────┘
                                     ▼
                          ┌───────────────────────┐
                          │  Feature Computation   │
                          │  (Indicators + Alpha)  │
                          └──────────┬────────────┘
                                     ▼
                          ┌───────────────────────┐
                          │  Alpha Factor IC Test  │
                          │  (Does it predict?)    │
                          └──────────┬────────────┘
                                     ▼
                 ┌───────────────────────────────────┐
                 │                                   │
                 ▼                                   ▼
        ┌─────────────────┐               ┌─────────────────┐
        │  YES (IC > 0)   │               │  NO (IC ≈ 0)    │
        │  Build Strategy │               │  Discard factor │
        └────────┬────────┘               └─────────────────┘
                 ▼
        ┌─────────────────┐
        │  Backtest       │
        │  (Simulator)    │
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │  Monte Carlo    │
        │  Validation     │
        └────────┬────────┘
                 ▼
        ┌─────────────────┐
        │  p < 0.05?      │
        └────────┬────────┘
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
  ┌──────────┐          ┌──────────┐
  │ YES      │          │ NO       │
  │ Proceed  │          │ Reject   │
  │ to       │          │ Strategy │
  │ Walk-    │          └──────────┘
  │ forward  │
  └────┬─────┘
       ▼
  ┌──────────┐
  │ gap < 0.3?│
  └────┬─────┘
       │
  ┌────┴────┐
  ▼         ▼
┌──────┐ ┌──────┐
│ YES  │ │ NO   │
│ Live │ │Tune  │
│ Trade│ │Filter│
└──────┘ └──────┘
```

---

## 7. Key Takeaways

1. **Alpha factors are hypotheses** — test them, don't assume they work
2. **Monte Carlo is your gatekeeper** — if p > 0.05, stop and rethink
3. **Walk-forward reveals stability** — a strategy that works in 2022 may fail in 2023
4. **News conditioning is the edge** — most quants ignore news, combining it with price signals is where alpha lives
5. **One change at a time** — otherwise you can't attribute improvements
6. **Signal before strategy** — no point building rules around a random signal

---

*Created: 2026-07-16*
*Part of the Advanced Trading System project*
