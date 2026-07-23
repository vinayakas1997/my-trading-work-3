# 00 — Vision: An Agent That Masters Stocks

> A trading system that learns from experience, diagnoses its own failures, and comes to understand each stock like an expert would — before risking real money.

---

## 1. The 3-Environment Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THE SYSTEM AT A GLANCE                              │
│                                                                             │
│  ┌──────────────────┐    ┌─────────────────────────┐    ┌──────────────────┐│
│  │  INITIAL-ANALYSIS │    │   RESEARCH-SIMULATIONS   │    │   LIVE-TRADING   ││
│  │  (deterministic)  │    │      (LLM-driven)        │    │  (deterministic) ││
│  │                   │    │                         │    │                  ││
│  │  What the stock   │───→│  Learn what works for   │───→│  Execute approved ││
│  │  does (data)      │    │  this stock (knowledge) │    │  strategies      ││
│  │                   │    │                         │    │                  ││
│  │  19 angles run    │    │  LLM generates & tests  │    │  Broker APIs     ││
│  │  No LLM at all    │    │  This is where the      │    │  Zero LLM calls  ││
│  │                   │    │  agent thinks           │    │                  ││
│  └──────────────────┘    └─────────────────────────┘    └──────────────────┘│
│           │                         │                          │              │
│           │                         │                          │              │
│           ▼                         ▼                          ▼              │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │                      DATA & MEMORY LAYER                              │    │
│  │                                                                       │    │
│  │  SQLite DB: past runs, metrics, hypothesis registry, strategy store   │    │
│  │  Parquet: angle results, indicator distributions, price data          │    │
│  │  Shared memory: what was tried, what worked, what failed, and WHY     │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**The rule:** LLMs only live inside Research-Simulations. Initial-Analysis and Live-Trading are fully deterministic — same inputs always produce same outputs. This prevents surprises during live trading.

---

## 2. The Problem: The Stateless Loop

The current Research-Simulations loop has a fatal flaw: **it has no memory**.

```
┌─────────────────────────────────────────────────────┐
│              THE STATELESS LOOP TODAY                │
│                                                     │
│  Run 1: JPM                                         │
│    Iter 1: RSI 30/70     → Sharpe 0.00              │
│    Iter 2: RSI + ADX     → Sharpe 0.00              │
│    Iter 3: RSI + SMA     → Sharpe 0.00              │
│    → STOP (gave up)                                  │
│                                                     │
│  Run 2: JPM (fresh start, doesn't remember run 1)   │
│    Iter 1: RSI 30/70     → Sharpe 0.00              │
│    Iter 2: RSI + ADX     → Sharpe 0.00              │── repeats same mistakes
│    Iter 3: RSI + Bollinger → Sharpe 0.00             │
│    → STOP (gave up)                                  │
│                                                     │
│  PROBLEM: The second run repeats the first run's     │
│  failures because the LLM doesn't know what was      │
│  tried before. Memory is never used.                 │
└─────────────────────────────────────────────────────┘
```

The research loop iterates, but it doesn't learn. It:
- Saves results to SQLite but **never reads them back**
- Only sees the **last** iteration's failure, not the full history
- Applies the **same** critic rules every time, even when they don't help
- Never asks **"why did I fail?"** — just tries again blindly

---

## 3. The Solution: The Memory-First Agent

The fix is to give the system **memory at every layer** — so it learns from experience, diagnoses root causes, and becomes an expert on each stock over time.

```
┌─────────────────────────────────────────────────────┐
│           THE MEMORY-FIRST AGENT (FUTURE)            │
│                                                     │
│  Past memory (from SQLite):                         │
│  "JPM: 3 runs, 15 iterations, all mean-reversion    │
│   failed. Momentum had 1 success. Avoid mean-rev."   │
│                                                     │
│  Run 3: JPM                                          │
│    Phase 0: "Let me understand JPM first..."         │
│      → Checks memory: "mean-reversion failed before" │
│      → Checks data: "JPM is trending (AR=0.95)"     │
│      → Conclusion: "Try momentum instead."          │
│                                                     │
│    Phase 1: Generate momentum strategy               │
│      → Backtest: Sharpe 0.35 (not great)             │
│      → Diagnosis: "signal too weak, try wider SMA"   │
│                                                     │
│    Phase 2: Refine with wider SMA                    │
│      → Backtest: Sharpe 0.60 (better)                │
│      → Diagnosis: "improving, continue"              │
│                                                     │
│    Phase 3: Grid search over SMA periods             │
│      → Best: SMA 50/200 → Sharpe 0.82                │
│      → Hypothesis: VALIDATED                          │
│      → Evidence saved: "SMA 50/200 works for JPM"    │
│                                                     │
│  Memory updated: "JPM momentum SMA 50/200 → 0.82"    │
│  Future runs will remember this.                     │
└─────────────────────────────────────────────────────┘
```

---

## 4. The 7 Cognitive Layers (How the Agent Thinks)

Each layer adds a capability. They build on each other like layers of a brain.

```
┌────────────────────────────────────────────────────────┐
│           THE 7 LAYERS OF AGENT INTELLIGENCE            │
│                                                         │
│  Layer 7: Goal Understanding ───────────────────────┐   │
│  "What does the user actually want? Is it possible?" │   │
│                                                      ▼   │
│  Layer 6: Seeking Information ──────────────────┐        │
│  "I'm stuck. Let me query the database first."   │        │
│                                                   ▼       │
│  Layer 5: Meta-Strategy ─────────────────┐               │
│  "Should I keep going or change approach?" │               │
│                                            ▼               │
│  Layer 4: Adaptive Reasoning ──────┐                      │
│  "This fix never helps. Stop using it."                    │
│                                     ▼                      │
│  Layer 3: Experience Memory ───────┐                      │
│  "Past runs show this fails on JPM."                       │
│                                     ▼                      │
│  Layer 2: Understanding ──────────┐                       │
│  "Let me check the stock's behavior first."                │
│                                    ▼                       │
│  Layer 1: Self-Diagnosis ────────┐                        │
│  "Why did I fail? Root cause?"                            │
│                                   ▼                        │
│  Layer 0: Execute Loop ──── (already built)               │
│  "Generate → backtest → critic → repeat"                  │
└────────────────────────────────────────────────────────┘
```

### Layer 0 — Execute Loop ✅ Already Built

```
User idea → generate code → backtest → critic → refine → repeat → validate
```

This is what `vinu-research` already does. It works, it just doesn't learn.

---

### Layer 1 — Self-Diagnosis 🟡 Build Next

**What it does:** After every failure, the agent asks "WHY?" before trying again.

```
Old way:                           New way:
Sharpe 0.00 → iterate              Sharpe 0.00 → DIAGNOSE
                                    ↓
                                   "0 trades because RSI threshold
                                    30/70 never triggered on JPM
                                    (RSI stays 35-65)"
                                    ↓
                                   "Relax thresholds or switch approach"
```

**Memory created:**
```
Failure Record:
  iteration: 2
  symptom: "0 trades"
  root_cause: "RSI range for JPM is 35-65, never hits 30/70 thresholds"
  action_taken: "relaxed thresholds to 20/80"
```

**Implementation:** Add a diagnosis step after backtest. If trade_count == 0 or Sharpe below threshold, the LLM analyzes why and records the root cause.

---

### Layer 2 — Understanding Before Acting 🟡 Build Next

**What it does:** Before writing any strategy code, the agent studies the stock's behavior.

```
┌──────────────────────────────────────────────┐
│              UNDERSTANDING PHASE              │
│                                              │
│  Input: symbol = JPM                         │
│                                              │
│  1. Fetch volatility: 15% annualized          │
│  2. Fetch RSI distribution: 35-65             │
│  3. Fetch auto-correlation: 0.95 (trending)  │
│  4. Fetch trend strength: ADX avg = 28        │
│                                              │
│  Analysis: "JPM is strongly trending, not    │
│  mean-reverting. RSI never hits extremes.    │
│  Momentum would be more appropriate."         │
│                                              │
│  Output: "Use momentum approach, SMA 50/200" │
└──────────────────────────────────────────────┘
```

**Memory created:**
```
Stock Profile:
  symbol: JPM
  vol: 15%, range: low
  rsi_range: 35-65
  trend: strong (ADX 28)
  recommended_strategies: ["momentum", "breakout"]
  avoid_strategies: ["mean_reversion"]
```

**Implementation:** Add a stock characterization step at the start of each run, before the loop. Store the profile for reuse.

---

### Layer 3 — Experience Memory 🟠 Core Upgrade

**What it does:** The agent remembers past runs and uses them to avoid repeating failures.

```
┌─────────────────────────────────────────────────────┐
│              EXPERIENCE MEMORY FLOW                   │
│                                                       │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────┐ │
│  │ New Run  │───→│ Query Memory │───→│ LLM sees:    │ │
│  │ starts   │    │             │    │ "Past 5 runs │ │
│  └──────────┘    │ SQLite DB   │    │  on JPM..."  │ │
│                  │ past results │    └──────────────┘ │
│                  │ per symbol   │                     │
│                  └─────────────┘                     │
│                         │                             │
│                         ▼                             │
│                  ┌─────────────┐                      │
│                  │ Add new     │                      │
│                  │ experience  │◄──── after run ends  │
│                  └─────────────┘                      │
│                                                       │
│  Memory snapshot injected into LLM prompt:            │
│  "Past research on JPM:                               │
│   Jul-10 RSI mean-rev → Sharpe 0.00 (0 trades)       │
│   Jul-15 SMA crossover → Sharpe 0.30 (12 trades)     │
│   Jul-18 Bollinger Bands → Sharpe 0.80 (ACTIVE)"      │
└─────────────────────────────────────────────────────┘
```

**Memory created:** A summary of past runs per symbol, injected into every new LLM prompt.

**Implementation:** Add a `query_past_runs(symbol)` method to `service.py`, call it before generating the LLM prompt, inject the summary.

---

### Layer 4 — Adaptive Reasoning 🟠 Core Upgrade

**What it does:** The critic learns which suggestions actually help and stops suggesting things that don't.

```
┌─────────────────────────────────────────────────────┐
│              ADAPTIVE CRITIC MEMORY                   │
│                                                       │
│  Iter 1: critic says "add ADX filter"                 │
│  Iter 2: ADX added, Sharpe unchanged                  │
│    → Memory: "ADX didn't help. Don't suggest again."  │
│                                                       │
│  Iter 2: critic says "use wider RSI thresholds"       │
│  Iter 3: RSI 20/80, Sharpe improved 0.00→0.20        │
│    → Memory: "wider RSI helped. Suggest earlier."     │
│                                                       │
│  By Iter 4, the critic only suggests things that       │
│  have actually shown improvement in previous iters.    │
└─────────────────────────────────────────────────────┘
```

**Memory created:**
```
Suggestion Memory:
  - "add ADX filter" → tried 2 times → never improved Sharpe → DISABLED
  - "widen RSI thresholds" → tried 1 time → improved 0.00→0.20 → KEEP
  - "use 1H timeframe" → never tried → suggest next
```

**Implementation:** Track `suggestion → was_applied → sharpe_change` in a dict. Before generating suggestions, filter out ineffective ones.

---

### Layer 5 — Meta-Strategy Reflection 🟠 Core Upgrade

**What it does:** After 2-3 failed iterations, the agent steps back and decides whether to pivot to a completely different approach.

```
┌─────────────────────────────────────────────────────┐
│              META-STRATEGY REFLECTION                 │
│                                                       │
│  After 2 failed iterations:                          │
│                                                       │
│  "My approach has failed 2 times with 0 trades.      │
│   The root cause is consistent: RSI never triggers    │
│   on JPM. Continuing to refine RSI is wasting time.  │
│                                                       │
│   Options:                                            │
│   A. Keep refining RSI (unlikely to work)             │
│   B. Pivot to momentum (different class)             │
│   C. Pivot to Bollinger (still mean-rev, different)  │
│   D. Ask for more data                                │
│                                                       │
│   Decision: Try B — momentum."                       │
└─────────────────────────────────────────────────────┘
```

**Memory created:**
```
Pivot Record:
  run_id: 42
  initial_approach: "RSI mean-reversion"
  iterations_tried: 2
  best_sharpe: 0.00
  pivot_reason: "RSI never triggers on JPM (range 35-65)"
  new_approach: "SMA crossover momentum"
  pivot_result: "Sharpe 0.60 — success"
```

**Implementation:** Add a `_reflect()` method in `loop.py`. Called after iteration 2 if Sharpe < 0.1 and trade count < 5. The LLM decides: continue, pivot, or stop.

---

### Layer 6 — Seeking Information 🟡 Medium Priority

**What it does:** The LLM can query tools for additional data when it's stuck.

```
┌─────────────────────────────────────────────────────┐
│              TOOL USE (FUNCTION CALLING)              │
│                                                       │
│  LLM: "I need RSI distribution for JPM"              │
│    → calls get_indicator_distribution("JPM", "RSI")  │
│    → gets: 10th=38, 50th=48, 90th=58                │
│    → "Ah, RSI is always 38-58. I need 35/65 min."    │
│                                                       │
│  LLM: "What strategies worked for JPM before?"        │
│    → calls get_past_strategies("JPM")                │
│    → gets: "momentum: 0.60, mean-rev: 0.00"          │
│    → "Don't try mean-reversion again."               │
└─────────────────────────────────────────────────────┘
```

**Tools the LLM can use:**
- `get_indicator_distribution(symbol, indicator, from, to)` — fetch percentile data
- `get_past_strategies(symbol, limit)` — fetch past run summaries
- `get_stock_profile(symbol)` — fetch volatility, trend, RSI range
- `get_indicator_availability(symbol)` — what indicators are computed
- `ask_user(message)` — ask the human for clarification

**Memory created:** Each tool call and result is logged for audit.

**Implementation:** Add function-calling to the LLM client. Define tool schemas. Execute tools when the LLM requests them.

---

### Layer 7 — Goal Understanding 🟠 Core Upgrade

**What it does:** Before starting, the agent validates whether the user's idea makes sense for this stock.

```
┌─────────────────────────────────────────────────────┐
│              GOAL UNDERSTANDING                       │
│                                                       │
│  User says: "mean-reversion strategy for JPM"        │
│                                                       │
│  Agent thinks:                                        │
│  "Mean-reversion exploits price oscillations.         │
│   Does JPM oscillate? Let me check...                 │
│   Auto-correlation: 0.95 (very persistent)            │
│   → JPM is strongly trending, not mean-reverting.     │
│   → A mean-reversion strategy will likely fail.       │
│   → I should warn the user."                          │
│                                                       │
│  Agent responds:                                      │
│  "JPM has strong trend persistence (AR=0.95).         │
│   Mean-reversion typically fails on trending stocks.  │
│   I recommend momentum instead. Proceed?"             │
└─────────────────────────────────────────────────────┘
```

**Memory created:**
```
Validation Record:
  user_idea: "mean-reversion JPM"
  data_checked: "auto-correlation=0.95, ADX=28"
  verdict: "not suitable"
  suggested_alternative: "momentum"
  user_accepted: true
```

**Implementation:** Add a `validate_hypothesis()` step before the loop. Check the idea against the stock's behavior data. If mismatched, flag to user.

---

## 5. The Hypothesis Registry (The Brain)

At the center of all 7 layers is the **Hypothesis Registry** — a structured memory that tracks everything the agent has learned about each stock.

```
┌─────────────────────────────────────────────────────────────┐
│                    HYPOTHESIS REGISTRY                        │
│                                                               │
│  Each hypothesis tracks:                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  hypothesis_id: "JPM-momentum-SMA-20260720"             │ │
│  │  symbol: JPM                                             │ │
│  │  thesis: "JPM trends strongly, momentum should work"     │ │
│  │  strategy_type: "momentum"                               │ │
│  │  indicators: ["sma_50", "sma_200"]                       │ │
│  │  state: "validated"  ← lifecycle: exploring→testing→    │ │
│  │  best_sharpe: 0.82          validated→rejected→monitoring│ │
│  │  evidence: [                                              │ │
│  │    {run_id: 42, iter: 1, sharpe: 0.35, conclusion:      │ │
│  │     "promising but weak"},                                │ │
│  │    {run_id: 42, iter: 3, sharpe: 0.82, conclusion:      │ │
│  │     "works with SMA 50/200, validated"}                  │ │
│  │  ]                                                        │ │
│  │  failure_reason: null  ← set when rejected               │ │
│  │  created: 2026-07-20                                      │ │
│  │  updated: 2026-07-20                                      │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                               │
│  The registry answers:                                        │
│  • "What approaches have been tried on JPM?"                 │
│  • "Which ones worked?"                                       │
│  • "Which ones failed — and WHY?"                            │
│  • "What evidence supports each conclusion?"                 │
└─────────────────────────────────────────────────────────────┘
```

**Lifecycle of a hypothesis:**

```
EXPLORING ──→ TESTING ──→ VALIDATED ──→ MONITORING
                │                       │
                ▼                       │
             REJECTED ◄─────────────────┘
                             (if decays)

- EXPLORING: Just thought of it, not tested yet
- TESTING: Currently being backtested
- VALIDATED: Evidence shows it works
- REJECTED: Evidence shows it doesn't work (with reason)
- MONITORING: Was validated but now being watched for decay
```

---

## 6. Patterns Worth Adopting from Other Repos

### From Vibe-Trading (HKUDS) — 3 patterns

| Pattern | Fits Layer | What It Adds |
|---------|-----------|-------------|
| Hypothesis registry with lifecycle | L3 + L7 | Structured memory of what was tried and WHY |
| Cross-session memory injection | L3 | Past run summaries fed into LLM prompts |
| Research autopilot | L5 | Closed loop: hypothesis → backtest → link evidence |

### From FinRL-Trading — 2 patterns

| Pattern | Fits Layer | What It Adds |
|---------|-----------|-------------|
| Audit log with reasoning | L1 | Full trail of every decision + WHY |
| Multi-stage decision pipeline | L2 | Regime → group → asset → risk → weights |

### From Qlib (Microsoft) — 1 pattern

| Pattern | Fits Layer | What It Adds |
|---------|-----------|-------------|
| Rolling strategy update | L4 | Incremental refinement instead of rebuild from scratch |

### From FinRL-Meta — 1 pattern

| Pattern | Fits Layer | What It Adds |
|---------|-----------|-------------|
| Turbulence risk overlay + cooldown | L4 | Emergency exit when market shocks; prevents rapid cycling |

---

## 7. Implementation Roadmap

### Phase 1 — Quick Wins (Memory Foundation)

These are small changes that give the system basic memory and self-awareness.

```
Week 1:
  ├── Layer 3: Inject past run summary into LLM prompt
  │     (~20 lines in service.py + llm_generator.py)
  │     Query SQLite, summarize, inject before generation.
  │     Effect: Agent stops repeating past failures.
  │
  ├── Layer 1: Add diagnosis after 0-trade failures
  │     (~25 lines in loop.py)
  │     If trade_count == 0: LLM analyzes root cause.
  │     Effect: Instead of blind iterating, agent knows WHY.
  │
  └── Layer 1: Add reasoning trail to IterationRecord
        (~15 lines in models.py)
        Store the LLM's rationale at each iteration.
        Effect: Full debug trail for post-mortem analysis.
```

**Total: ~60 lines of code.**

### Phase 2 — Core Intelligence (Hypothesis + Pivot)

```
Week 2-3:
  ├── Layer 3+7: Extend hypothesis registry with lifecycle
  │     (~60 lines in hypothesis_registry.py)
  │     Add states, evidence, invalidation reason.
  │     Effect: Structured learning memory across all runs.
  │
  ├── Layer 2: Add stock characterization before the loop
  │     (~50 lines in loop.py + new prompt)
  │     Fetch volatility, RSI range, ADX, auto-correlation.
  │     Effect: Strategy choice is data-driven, not guessed.
  │
  └── Layer 5: Add meta-strategy reflection step
        (~40 lines in loop.py)
        After 2+ failures, LLM decides: continue, pivot, or stop.
        Effect: Agent doesn't waste iterations on dead ends.
```

**Total: ~150 lines of code.**

### Phase 3 — Advanced Agency

```
Week 4+:
  ├── Layer 4: Track suggestion effectiveness
  │     (~30 lines in loop.py)
  │     Filter out suggestions that never help.
  │     Effect: Critic improves over time.
  │
  ├── Layer 7: Validate user's idea against stock data
  │     (~30 lines in loop.py)
  │     Check if the requested approach fits the stock.
  │     Effect: Catch impossible requests early.
  │
  ├── Layer 6: Add tool use (function calling)
  │     (~80 lines in llm.py + tool definitions)
  │     Let LLM query data services when stuck.
  │     Effect: Agent can seek its own information.
  │
  └── Layer 4: Add turbulence risk overlay to simulator
        (~30 lines in simulator service)
        Emergency exit when market shocks hit.
        Effect: Live trading safety.
```

**Total: ~170 lines of code.**

---

## 8. Memory Flow Diagram (End to End)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     FULL MEMORY FLOW DIAGRAM                              │
│                                                                          │
│  INITIAL-ANALYSIS                                                       │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  19 angles compute stock data → stored in Parquet + SQLite        │ │
│  │  Includes: trend lifecycle, regime, RSI distrib, volatility, etc. │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  RESEARCH-SIMULATIONS                                                    │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                                                                      │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ L7: Goal Check    │── "Is this idea suitable for this stock?"    │ │
│  │  └───────────────────┘                                               │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ L3: Memory Query  │── Reads SQLite for past runs on this symbol  │ │
│  │  └───────────────────┘                                               │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ L2: Understanding │── Fetches stock profile (vol, RSI range, etc) │ │
│  │  └───────────────────┘                                               │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────────────────────────┐                          │ │
│  │  │          THE ITERATION LOOP            │                          │ │
│  │  │                                        │                          │ │
│  │  │  ┌──────────┐   ┌──────────┐   ┌─────┴──────┐                   │ │
│  │  │  │ Generate  │──→│ Backtest │──→│ L1: Self-  │                   │ │
│  │  │  │ Strategy  │   │          │   │ Diagnosis  │                   │ │
│  │  │  └──────────┘   └──────────┘   └─────┬──────┘                   │ │
│  │  │                                      │                            │ │
│  │  │         ┌────────────────────────────┘                            │ │
│  │  │         ▼                                                         │ │
│  │  │  ┌──────────────────────────┐                                    │ │
│  │  │  │ L5: Meta-Reflection?    │── After 2 fails: pivot? continue?   │ │
│  │  │  └──────────────────────────┘                                    │ │
│  │  │         │                                                         │ │
│  │  │         ▼                                                         │ │
│  │  │  ┌──────────┐                                                    │ │
│  │  │  │ L4:      │── Adaptive critic filters ineffective suggestions   │ │
│  │  │  │ Critic   │                                                    │ │
│  │  │  └──────────┘                                                    │ │
│  │  │         │                                                         │ │
│  │  │    PASS/STOP/REFINE                                               │ │
│  │  └───────────────────────────────────────────────────┘              │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ Save to Memory:   │── Updates SQLite + Hypothesis Registry       │ │
│  │  │ hypothesis state  │   with evidence, metrics, reasoning          │ │
│  │  │ evidence, metrics │                                               │ │
│  │  └───────────────────┘                                               │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ Validate:         │── Walk-forward + stress test + holdout        │ │
│  │  │ walk-fwd, stress  │                                               │ │
│  │  └───────────────────┘                                               │ │
│  │          │                                                           │ │
│  │          ▼                                                           │ │
│  │  ┌───────────────────┐                                               │ │
│  │  │ Approve → Artifact│── Strategy saved as ACTIVE                   │ │
│  │  └───────────────────┘                                               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  LIVE-TRADING                                                            │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Execute approved strategy against broker                           │ │
│  │  No LLM calls. Deterministic execution.                             │ │
│  │                                                                      │ │
│  │  When decay detected: trigger re-research                            │ │
│  │  → Research-Simulations already has past memory ready                │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                  │                                       │
│                                  ▼                                       │
│  FEEDBACK LOOP                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │  Live PnL attribution → feeds back to Initial-Analysis              │ │
│  │  Strategy decay → triggers re-research (with experience memory)     │ │
│  │  Each re-research is smarter than the last                          │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 9. Summary

| Question | Answer |
|----------|--------|
| **What are we building?** | A Research-Simulations agent that learns from experience, diagnoses failures, and becomes an expert on each stock before live trading |
| **How?** | 7 cognitive layers, each adding a dimension of memory or self-awareness |
| **What stays unchanged?** | Initial-Analysis (deterministic, 19 angles) — no LLM needed. Live-Trading (deterministic execution) — no LLM at runtime |
| **What's the quickest win?** | Inject past run summaries into LLM prompts (~20 lines). Immediately stops repeating same failures |
| **What's the most advanced?** | Meta-strategy reflection (pivot decisions) and hypothesis registry (full learning memory) |
| **Are the reference repos useful?** | Vibe-Trading is the most relevant (hypothesis lifecycle, memory injection, autopilot). FinRL contributes audit log and multi-stage pipeline. Qlib contributes rolling updates |
| **When is it "done"?** | When the agent can: (1) remember past attempts, (2) diagnose why it failed, (3) pivot to better approaches, (4) validate hypotheses with evidence, and (5) warn the user when their idea doesn't fit the stock |

---

## 10. Files to Keep / Delete

After this file is created, the other 3 files are no longer needed as standalone docs:

| File | Action | Reason |
|------|--------|--------|
| `00-vision.md` | ✅ **KEEP** | This file — the single source of truth |
| `01-improvement.md` | ❌ Delete | Content absorbed into sections 2-3 |
| `02-cognitive-layers.md` | ❌ Delete | Content absorbed into section 4 |
| `03-reference-patterns.md` | ❌ Delete | Content absorbed into section 6 |

All implementation details (code snippets, line numbers, etc.) are preserved in the
actual codebase (`loop.py`, `llm_generator.py`, etc.) — they never belonged in docs.
