# 02 — Cognitive Layers for True Agency

> What makes an agent "master of itself" — able to observe, reason, diagnose, adapt, and autonomously decide what to do without being told.

## The Problem: Your Current Agent Has No Self-Awareness

The research loop executes well, but it doesn't **think** about what it's doing.

```
Iteration 1: code → backtest → Sharpe 0.00 → critic says "add ADX filter"
Iteration 2: code + ADX → backtest → Sharpe 0.00 → critic says "add ADX filter" (AGAIN!)
Iteration 3: code + ADX (already there) → backtest → Sharpe 0.00 → give up
```

The agent never stops to ask: "**Why** is my Sharpe 0.00? Is the problem really no ADX filter?"

## The 7 Cognitive Layers

Each layer adds a capability that makes the agent progressively more self-aware, adaptive, and intelligent.

```
Layer 7: Goal Understanding — "WHY am I doing this? Is it possible?"
Layer 6: Seeking Information  — "I'm stuck. What do I need to learn?"
Layer 5: Meta-Strategy        — "Should I keep going or change approach?"
Layer 4: Adaptive Reasoning   — "This suggestion never helps. Stop it."
Layer 3: Experience Memory    — "Past runs failed this way. Try something else."
Layer 2: Understanding        — "Let me understand this stock first."
Layer 1: Self-Diagnosis       — "Why did I fail? What was the actual problem?"
```

---

## Layer 1: Self-Diagnosis (Easiest → Highest ROI)

**Current behavior:** After a failure, the agent just iterates with non-specific feedback.

**What a master agent would do:**

```
Iteration 1 fails with 0 trades:
  → Not just "Sharpe 0.00"
  → Actually analyze: "I had 0 trades because my RSI threshold (30/70) 
     was never triggered. Let me check: what is the actual RSI range 
     for JPM over this period? If RSI stays between 35-65, then 
     RSI mean-reversion with 30/70 will NEVER produce trades."
  → Diagnosis: "Wrong indicator thresholds for this stock's volatility profile."
  → Next action: "Before iterating, check the RSI distribution."
```

**Implementation in loop.py:**

After `result` is returned and if `result.trade_count == 0`:

```python
if result.trade_count == 0:
    diagnosis = await self._llm.analyze_failure(
        strategy_code=strategy_code,
        metrics=result.metrics,
        symbol=symbol,
        from_date=research_from,
        to_date=research_to,
    )
```

Add a new LLM prompt that takes the code + 0-trade result and asks:
> "The above strategy produced 0 trades. Why? What is the root cause? 
>  Is it: wrong indicator choice? wrong thresholds? wrong timeframe?
>  missing conditions? data issue? Or fundamentally wrong approach?"

**LoC estimate:** ~15 lines in `loop.py`, ~40 lines for a new prompt function.

---

## Layer 2: Understanding Before Acting

**Current behavior:** The user provides an idea → the agent immediately writes code.

**What a master agent would do:**

Before writing ANY code, it studies the stock:

```
Phase 0 — Stock Characterization:
  1. Fetch 1-year daily returns for JPM
  2. Compute: volatility (daily, weekly), RSI distribution, 
     SMA cross count, average true range, beta
  3. LLM analyzes: "JPM has low volatility (15% annualized), 
     RSI range is 35-65 (never extreme), mean daily range is 1.2%. 
     This is NOT a good candidate for mean-reversion. 
     Momentum or trend-following would be more appropriate."
  4. If user requested mean-reversion: flag the mismatch and suggest alternative
```

**Implementation:**

Add a `characterize_stock(symbol, from_date, to_date)` step before the main loop:

```python
characterization = await characterize_stock(
    symbol, research_from, research_to,
    tools=self._tools,
    llm=self._llm,
)
prompt += f"\n\nStock characterization:\n{characterization}"
```

**LoC estimate:** ~30 lines in `loop.py`, ~30 lines for characterization function + prompt.

---

## Layer 3: Experience Memory

**Current behavior:** Each research run starts from scratch. No memory of past runs.

**What a master agent would do:**

Before generating a strategy, query past runs:

```
Past runs for JPM (from SQLite):
  Run #42 (2026-07-01): mean-reversion RSI → Sharpe 0.00 (0 trades)
  Run #43 (2026-07-02): meaneversion RSI (wider thresholds) → Sharpe 0.00 (0 trades)
  Run #44 (2026-07-05): SMA crossover momentum → Sharpe 0.30 (12 trades, WR 42%)
  Run #45 (2026-07-08): Bollinger Bands → Sharpe 0.80 (ACTIVE)

Observation: Mean-reversion consistently fails on JPM. Momentum works.
Recommendation: Do NOT attempt mean-reversion again. If user requested it,
  inform them and suggest momentum instead.
```

**Implementation:**

1. Add a method to query past runs by symbol from `ResearchStorage`
2. Build a compact summary string
3. Inject into the LLM generation prompt

```python
past_runs = await self._storage.get_runs_by_symbol(symbol, limit=10)
summary = summarize_past_runs(past_runs)
prompt += f"\n\nPast research on {symbol}:\n{summary}"
```

**LoC estimate:** ~20 lines in `service.py`, ~15 lines for summarization.

---

## Layer 4: Adaptive Reasoning (The Critic That Learns)

**Current behavior:** The critic applies the same rules every time. "Sharpe < 0.5 → add ADX filter" — even if ADX was already added and didn't help.

**What a master agent would do:**

The critic tracks which suggestions were applied and their effect:

```
Suggestion history for this run:
  Iter 1 → critic: "add ADX filter"
  Iter 2 → ADX added, Sharpe still 0.00 → "add ADX filter" was WRONG
  Iter 3 → should NOT suggest ADX again. Try different suggestion.

Suggestion memory for this symbol across runs:
  JPM Run #42: "add ADX filter" → no improvement
  JPM Run #43: "add ADX filter" → no improvement
  Learning: ADX filter never helped JPM. Stop suggesting it.
```

**Implementation:**

Track a `suggestion_history` dict per run:

```python
self._suggestion_results = {}  # suggestion_text → [was_applied, sharpe_improved]

def _filter_ineffective_suggestions(self, base_suggestions, suggestion_results):
    effective = []
    for s in base_suggestions:
        if s in suggestion_results and not suggestion_results[s]:
            continue  # Skip — has been tried and didn't help
        effective.append(s)
    return effective
```

**LoC estimate:** ~25 lines in `loop.py`.

---

## Layer 5: Meta-Strategy (The Reflection Step)

**Current behavior:** The agent commits to one approach (e.g., RSI mean-reversion) and refines it for all iterations — even if it's clearly failing.

**What a master agent would do:**

After each iteration, step back and ask:

```
Reflection after iteration 2:
  Current approach: RSI mean-reversion with SMA filter
  Performance: 0 trades, Sharpe 0.00 through 2 iterations
  Diagnosis: "RSI never triggers because JPM's RSI stays between 35-65"
  
  Options:
  A. Continue refining RSI (unlikely to work — fundamental approach wrong)
  B. Pivot to SMA crossover momentum (different strategy class)
  C. Pivot to Bollinger Bands (still mean-reversion, but different mechanism)
  D. Stop entirely (no viable strategy for JPM with available indicators)
  
  Decision: Try option B — momentum approach with SMA crossover.
```

**Implementation:**

Add a `_reflect()` method called after iteration 2 if Sharpe < threshold:

```python
async def _reflect(self, history, result):
    if len(history) < 2:
        return "continue"
    if all(h.result.sharpe < 0.1 for h in history[-2:]):
        pivot = await self._llm.suggest_pivot(
            user_idea=self._user_idea,
            symbol=self._symbol,
            history=[(h.result, h.critique) for h in history],
        )
        return pivot
    return "continue"
```

**LoC estimate:** ~30 lines in `loop.py`, ~30 lines for the LLM reflection prompt.

---

## Layer 6: Seeking Information (Tool Use)

**Current behavior:** The LLM only receives whatever the framework puts in its prompt. It can't ask for more information.

**What a master agent would do:**

The LLM can **call tools** when it needs more data:

```
Agent: "I need to understand RSI behavior for JPM before writing this strategy."
  → calls tools.get_indicator_distribution("JPM", "RSI_14", from_date, to_date)
  → gets back: percentiles [10th=38, 50th=48, 90th=58]
  → "So RSI is always between 38-58. My thresholds need to be 35/65 minimum."
```

**Implementation:**

Give the LLM a function-calling interface:

```python
TOOLS = [
    {
        "name": "get_indicator_distribution",
        "description": "Get percentile distribution of an indicator for a symbol",
        "parameters": {"symbol": "str", "indicator": "str", "from_date": "str", "to_date": "str"}
    },
    {
        "name": "get_past_strategies",
        "description": "Get past research runs for a symbol",
        "parameters": {"symbol": "str", "limit": "int"}
    },
    {
        "name": "get_stock_volatility",
        "description": "Get volatility statistics for a symbol",
        "parameters": {"symbol": "str", "period_days": "int"}
    },
]
```

**LoC estimate:** ~50 lines for tool definitions + executor. Requires function-calling capable LLM.

---

## Layer 7: Goal Understanding

**Current behavior:** The system takes a user's idea at face value and optimizes for Sharpe ratio without questioning whether the idea makes sense.

**What a master agent would do:**

Before starting, the agent validates the user's request:

```
User says: "Develop a mean-reversion strategy for JPM"

Agent's internal reasoning:
  Step 1: "Mean-reversion exploits price oscillations around a fair value."
  Step 2: "Does JPM oscillate? Let me check auto-correlation and mean-reversion half-life."
  Step 3: Fetches data → JPM's AR(1) coefficient = 0.95 (very persistent, not mean-reverting)
  Step 4: "JPM is strongly trending, not mean-reverting. A mean-reversion strategy will
          likely fail. I should inform the user and suggest momentum instead."
  
Agent responds: "Your request for JPM mean-reversion may not be optimal — JPM
  shows strong trend persistence (AR=0.95). I recommend momentum instead."
```

**Implementation:**

Add a `validate_hypothesis()` step:

```python
hypothesis = parse_user_idea(user_idea)
validation = await validate_approach(
    hypothesis, symbol, from_date, to_date, self._tools, self._llm
)
if validation["is_suitable"] == False:
    return {"warning": f"{hypothesis.strategy_type} may not work for {symbol}.",
            "suggested_alternative": validation["suggested_alternative"]}
```

**LoC estimate:** ~25 lines in `loop.py`, ~30 lines for LLM validation prompt.

---

## Implementation Roadmap

| Phase | Layer | What to Build | Effort | Impact |
|-------|-------|---------------|--------|--------|
| **1** | Layer 1 | Self-diagnosis after 0-trade failures | Low | 🔴 High |
| **1** | Layer 3 | Experience memory from SQLite | Low-Medium | 🔴 High |
| **2** | Layer 5 | Meta-strategy reflection step | Medium | 🟠 Medium-High |
| **2** | Layer 2 | Stock characterization before loop | Medium | 🟠 Medium |
| **3** | Layer 4 | Adaptive critic (track suggestion efficacy) | Low-Medium | 🟠 Medium |
| **3** | Layer 7 | Goal/hypothesis validation | Medium | 🟡 Medium |
| **4** | Layer 6 | Tool use (function calling for LLM) | High | 🟡 Low-Medium |

## Relationship to 01-improvement.md

| 01-improvement.md Gap | Corresponding Cognitive Layer |
|----------------------|------------------------------|
| Strategy memory across runs | Layer 3 (Experience Memory) |
| Cross-iteration state memory | Layer 1 (Self-Diagnosis) |
| Adaptive critic | Layer 4 (Adaptive Reasoning) |
| Meta-learning | Layer 3 + Layer 4 combined |
| Systematic exploration | Layer 5 (Meta-Strategy) |
| Planning-reflection loop | Layer 5 (Meta-Strategy) |
| Tool use | Layer 6 (Seeking Information) |

The `01-improvement.md` focuses on **structural code changes** (what to add to the loop).
This file (`02-cognitive-layers.md`) focuses on **how the agent thinks** — the cognitive capabilities that justify those structural changes.
