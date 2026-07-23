# 01 — Agentic Behavior Analysis & Improvement Plan

## Current State: The Stateless Loop

The research system iterates well but **doesn't learn**. Each run is an isolated loop with no memory of past experiences, no adaptation mid-loop, and no knowledge transfer across runs.

```
For each run:
  For each iteration:
    ├── Generate strategy (LLM or template)
    ├── Backtest
    ├── Critic → PASS/REFINE/STOP
    └── If REFINE: pass only last iteration to LLM
  End
Save result (never looked at again)
End
```

## What The Loop CAN Do Today

| Capability | Where | Mechanism |
|-----------|-------|-----------|
| Iterate | `loop.py:194` | `for iteration in range(1, max_iterations+1)` |
| Generate 3 candidates & rank | `llm_generator.py:292-324`, `comparison.py:19-67` | `asyncio.gather` + complexity/scoring |
| Critique by rules + LLM boost | `loop.py:909-1131` | Hardcoded thresholds + optional LLM override |
| Gate via holdout | `loop.py:304-332` | Re-backtest on unseen data |
| Post-loop validation | `loop.py:370-421` | Walk-forward + stress test + benchmark |
| Decay monitoring | `cli.py:450-520` | Track ACTIVE → DECAYED, auto re-research |

## What The Loop CANNOT Do

### 1. No Strategy Memory Across Runs

Each `POST /research/run` starts from scratch. The SQLite database stores every past run
(`ResearchStorage`, `SqliteStrategyStore`), but **nothing reads it before starting a new one**.

```
Run 1: JPM mean-reversion → Sharpe 0.00 → save to DB (buried)
Run 2: JPM momentum     → Sharpe 0.00 → save to DB (buried)
Run 3: JPM mean-reversion (fresh) → repeats the same mistakes
```

The LLM prompt has no context about:
- What was tried before on this symbol
- Which approaches historically failed or succeeded
- What the typical Sharpe/risk profile looks like

**Fix:** Before each run, query the past N runs for the same symbol. Inject a summary into the
LLM prompt: *"Past 5 runs on JPM tried mean-reversion (Sharpe 0.00), momentum (Sharpe 0.12), 
breakout (Sharpe -0.05). Try a different approach."*

---

### 2. No Cross-Iteration State Memory

The `history` list in `loop.py` tracks every iteration, but only the **last** iteration's
code/metrics/critique are passed to the LLM during refinement.

```
Iteration 1: low RSI → Sharpe 0.00, critic: "add trend filter"
Iteration 2: low RSI + SMA filter → Sharpe 0.00 (critic doesn't know this was tried before)
Iteration 3: low RSI + ADX filter → Sharpe 0.00 (same blind spot)
```

The LLM doesn't know **why** iteration 1 failed — only that it did. It might suggest
approach A (tried in iteration 1) again in iteration 3, wasting cycles.

**Fix:** Pass a condensed history of ALL prior iterations to the refinement prompt:
```
Iteration history:
  1: RSI 30/70, SMA crossover → Sharpe 0.00 (0 trades) — signal too strict
  2: RSI 20/80, SMA crossover → Sharpe 0.00 (0 trades) — still too strict
  3: RSI 20/80, ADX filter → Sharpe 0.00 (0 trades) — ADX didn't help
  Current suggestion: try without any trend filter, pure RSI on 1H data
```

---

### 3. No Adaptive Critic

The critic (`_rule_based_check`, lines 909-1083) uses **hardcoded thresholds** that never
change across iterations or runs:

```python
if sharpe < 0.5:  # Same every time
    suggestions.append("add ADX filter to avoid choppy markets")
```

If the critic said "add ADX filter" in iteration 1, and iteration 2 has ADX but still
fails, iteration 3's critic says "add ADX filter" **again** — it doesn't learn that ADX
didn't help.

**Fix:** Track which suggestions were applied and whether they improved metrics. If a
suggestion was tried and failed, skip it or downgrade its priority in future iterations.

---

### 4. No Meta-Learning / Pattern Recognition

No component asks fundamental questions:

- "Which indicators produced the highest Sharpe on this symbol historically?"
- "What strategy pattern (mean-reversion vs momentum vs breakout) works best for banks?"
- "Does RSI 30/70 ever work, or is it always zero-trades?"

The data exists in SQLite (hundreds of past runs), but it's never mined for patterns.

**Fix:** Add a lib query that scans past runs for correlations between strategy
characteristics and outcomes. Inject findings into the LLM prompt before generation.

---

### 5. No Systematic Exploration

The LLM proposes a strategy idea → writes code → tests → result. There's no structured
parameter search:

- "What if RSI oversold=10 vs 20 vs 30?"
- "What if SMA fast=10 vs 20 vs 50?"
- "What if we try all 9 combos and pick the best?"

Instead, the LLM guesses one set of parameters and refines from there.

**Fix:** After a successful strategy is found, run a grid search over its key parameters
(3 values × 3 values = 9 backtests). Select the best parameter set.

---

### 6. No Planning-Reflection Loop

Current flow: `Idea → Code → Test → Result`

True agentic flow: `Idea → Plan → Code → Test → Reflect → Revise Plan → Code → ...`

The LLM never plans the approach before writing code. It doesn't reflect on the full
trajectory of the run and change its overall strategy.

**Fix:** Add a planning step at the start of each run and a reflection step after
iteration 2+. The reflection feeds back into the plan.

```
Iteration 1: Plan(RSI mean-reversion) → Code → Test(Sharpe 0.00) → Reflect("no trades")
Iteration 2: Plan(relax constraints + use 1H data) → Code → Test(Sharpe 0.00) → Reflect("still no trades, try different indicator")
Iteration 3: Plan(Bollinger Bands) → Code → Test(Sharpe 0.80) → PASS
```

---

### 7. No Tool Use

The LLM doesn't call tools — it only generates code. It can't:
- Query the SQLite database for past results
- Run a quick analysis on raw price data
- Check which indicators are available
- Inspect the simulator's data schema

All of these are done by the framework before the LLM sees the prompt. The LLM is a
code generator, not an agent.

**Fix:** Give the LLM function-calling capabilities (tools) to query data, check
indicator availability, inspect past runs, and run quick analyses.

---

## Priority Matrix

| # | Capability | Effort | Impact | Suggested Order |
|---|-----------|--------|--------|-----------------|
| 1 | Strategy memory across runs | Low-Medium | 🔴 High | **1st** |
| 2 | Cross-iteration state memory | Low | 🔴 High | **2nd** |
| 6 | Planning-reflection loop | Medium | 🟠 Medium-High | **3rd** |
| 3 | Adaptive critic | Low-Medium | 🟠 Medium | **4th** |
| 5 | Systematic parameter search | Medium | 🟠 Medium | **5th** |
| 7 | Tool use for LLM | High | 🟡 Medium | **6th** |
| 4 | Meta-learning | High | 🟡 Low-Medium | **7th** |

## Recommended First Step

**Strategy memory across runs** is the highest ROI:

1. Add a query in `loop.py:run()` that fetches last 5 runs for the symbol from SQLite
2. Build a compact summary: *"Past results for JPM: Run#3 (2026-06-01) tried RSI mean-reversion → Sharpe 0.00, win rate 0% (0 trades). Run#4 tried SMA crossover → Sharpe 0.30, WR 35%. Run#5 tried Bollinger Bands → Sharpe 0.80, WR 52% (ACTIVE)."*
3. Inject this into the LLM generation prompt so the model avoids repeating failed approaches

### Estimated LoC: ~40 lines added to `loop.py` + `service.py`
