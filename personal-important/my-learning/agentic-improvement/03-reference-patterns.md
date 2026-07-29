# 03 — Reference Repo Pattern Analysis & Adaptation Guide

> What patterns from Qlib, FinRL-Meta, FinRL-Trading, and Vibe-Trading (HKUDS) are worth adopting for your agentic cognitive layers — without copying their code.

---

## How the Reference Repos Map to Your Cognitive Layers

```
Cognitive Layer           Best Pattern Source
────────────────────────────────────────────────────────────
L7: Goal Understanding    ← Vibe-Trading (goal lifecycle, evidence tracking)
L6: Seeking Information   ← Vibe-Trading (ReAct loop, tool batching, swarm)
L5: Meta-Strategy         ← Vibe-Trading (research autopilot, hypothesis lifecycle)
L4: Adaptive Reasoning    ← Qlib (rolling strategy update), FinRL (turbulence, cooldown)
L3: Experience Memory     ← Vibe-Trading (persistent memory, hypothesis registry)
L2: Understanding         ← Qlib (nested execution), FinRL (adaptive rotation engine)
L1: Self-Diagnosis        ← FinRL-Trading (audit log with reasoning)
```

---

## Repo-by-Repo: What to Adopt

### 1. Vibe-Trading (HKUDS) — The Most Relevant Repo

**Why it matters:** It's the only repo that treats the LLM as a true autonomous agent with:
hypothesis management, persistent memory, goal-driven execution, and tool use.

**Patterns to adopt:**

#### Pattern 1A: Hypothesis Registry with Lifecycle

**What it does:**
```python
# Vibe-Trading's hypothesis lifecycle:
# exploring → testing → validated → rejected → monitoring
#
# Each hypothesis stores:
#   - title, thesis, signal definition, data sources
#   - linked backtest run cards with metrics
#   - invalidation notes (WHY it was rejected)
#   - evidence records with source provenance
```

**Why adopt:** Your project has `hypothesis_registry.py` already, but it's a simple CRUD
store. It doesn't track lifecycle states, evidence, or reasoning. Adding these makes
your hypothesis registry a true "learning memory" — queries like "what approaches
failed for JPM and why?" become answerable.

**Implementation sketch:**
```python
class HypothesisState(enum.Enum):
    EXPLORING = "exploring"
    TESTING = "testing"
    VALIDATED = "validated"
    REJECTED = "rejected"
    MONITORING = "monitoring"

class Hypothesis(BaseModel):
    id: str
    symbol: str
    thesis: str
    strategy_type: str
    indicators_used: list[str]
    params_tested: dict
    best_result: BacktestResult | None
    evidence: list[Evidence]
    state: HypothesisState
    invalidation_reason: str | None
    created_at: datetime
    updated_at: datetime
```

**LoC estimate:** ~60 lines added to existing `hypothesis_registry.py`.

---

#### Pattern 1B: Research Autopilot Loop

**What it does:**
```python
# Vibe-Trading's autopilot:
# hypothesis → scaffold signal engine → generate backtest config →
# execute backtest → link metrics back to hypothesis
```

**Why adopt:** Your loop does steps 2-4, but step 1 and 5 are missing. Without them,
the agent doesn't know WHY it's testing something, and after testing, doesn't
connect the result back to the hypothesis. This is Layer 5 (meta-strategy).

**Implementation sketch (integrate into loop.py):**
```python
hypothesis = self._hypothesis_registry.get_active(symbol)
if hypothesis is None:
    hypothesis = await self._propose_hypothesis(symbol, user_idea, angles)
    self._hypothesis_registry.create(hypothesis)

evidence = Evidence(
    run_id=run_id, iteration=iteration, metric="sharpe",
    value=result.sharpe,
    conclusion="supports" if result.sharpe > threshold else "contradicts",
    reasoning=critique.reasoning,
)
hypothesis.add_evidence(evidence)
```

**LoC estimate:** ~40 lines added to `loop.py`.

---

#### Pattern 1C: Persistent Cross-Session Memory

**What it does:**
```python
# Vibe-Trading stores memory in ~/.vibe-trading/memory/
# LLM can save/recall/forget across sessions
# Memory snapshot is injected into the system prompt at session start
```

**Why adopt:** Your project saves runs to SQLite but never reads them before starting.
This pattern makes past experience part of the LLM's active context. It's the simplest
way to implement Layer 3 (experience memory).

**Implementation sketch (in llm_generator.py):**
```python
def _build_memory_context(symbol: str, storage: ResearchStorage) -> str:
    past_runs = storage.get_recent_runs(symbol, limit=5)
    if not past_runs:
        return ""
    memory_lines = [f"Past research on {symbol}:"]
    for run in past_runs:
        memory_lines.append(
            f"  [{run.created_at.date()}] {run.user_idea[:50]} → "
            f"Sharpe {run.best_sharpe:.2f}, {run.total_iterations} iters, "
            f"outcome={run.status}"
        )
    return "\n".join(memory_lines)
```

**LoC estimate:** ~25 lines.

---

### 2. FinRL-Trading — The Execution Layer

#### Pattern 2A: Audit Log with Full Reasoning Trail

**What it does:**
```python
# Every decision produces a full audit trail:
#   Regime detected: bull
#   Group selected: tech
#   Asset ranked: AAPL #1 (score=0.85)
#   Risk check: PASS (turnover=12% < limit=20%)
#   Reasoning: "Strong momentum, low volatility, bullish macro"
```

**Why adopt:** Your system logs metrics but never **reasoning**.
When you look at a failed run, you see Sharpe=0.00 but you don't know WHY the agent
chose that strategy or what it was thinking at each step.

**Implementation sketch (add to IterationRecord):**
```python
class DecisionRecord(BaseModel):
    iteration: int
    hypothesis: str
    approach_chosen: str
    alternatives_considered: list[str]
    reasoning: str
    expected_outcome: str
    actual_result: BacktestResult
    diagnosis: str | None
```

**LoC estimate:** ~30 lines in `models.py`, ~15 lines in `loop.py`.

---

### 3. Qlib — The Feature & ML Forecasting Engine

#### Pattern 3A: Rolling Strategy Update

**What it does:**
```python
# Qlib's OnlineStrategy:
#   - When new data arrives → generate rolling retraining tasks
#   - Models periodically retrained on fresh data
#   - Closed loop: train → predict → serve → update → retrain
```

**Why adopt:** Your system re-researches when decay is detected, but it starts from
scratch. Qlib's rolling strategy **incrementally updates** existing models rather
than rebuilding from zero.

**Implementation sketch (in service.py):**
```python
async def refresh_strategy(strategy_id: str) -> str:
    strategy = await storage.get_strategy(strategy_id)
    new_data = await fetch_fresh_data(strategy.symbol, strategy.last_data_date)
    refined_code = await llm.refine_with_new_data(
        strategy.code, strategy.result, new_data
    )
    new_result = await backtest(refined_code, strategy.symbol, new_data_dates)
    if new_result.sharpe > strategy.best_sharpe * 0.8:
        return refined_code
    else:
        return await full_re_research(strategy)
```

**LoC estimate:** ~40 lines in `service.py`.

---

### 4. FinRL-Meta — The Simulation Environment

#### Pattern 4A: Turbulence Risk Overlay + Cooldown

**What it does:**
```python
# When market turbulence exceeds threshold → sell all positions
# Cooldown prevents rapid buy-sell cycling after stop-loss triggers
```

**Why adopt:** Your simulator doesn't have a "turbulence mode" — a circuit breaker
that exits all positions when market conditions become extreme.

**Implementation sketch (in simulator):**
```python
class TurbulenceOverlay:
    def __init__(self, threshold: float = 0.5, cooldown_bars: int = 10):
        self.threshold = threshold
        self.cooldown_remaining = 0
    
    def should_exit(self, market_data: pd.Series) -> bool:
        if self.cooldown_remaining > 0:
            self.cooldown_remaining -= 1
            return False
        turbulence = compute_turbulence(market_data)
        if turbulence > self.threshold:
            self.cooldown_remaining = self.cooldown_bars
            return True
        return False
```

**LoC estimate:** ~30 lines in the simulator service.

---

## Combined Priority Matrix

All patterns ranked by impact × ease of implementation:

| # | Pattern | Source | Cognitive Layer | Effort | Impact | Phase |
|---|---------|--------|-----------------|--------|--------|-------|
| 1 | Inject past run summary into LLM prompt | Vibe-Trading | L3 | Very Low (~20 lines) | 🔴 High | 1 |
| 2 | Hypothesis registry with lifecycle | Vibe-Trading | L3 + L7 | Low (~60 lines) | 🔴 High | 1 |
| 3 | Audit log with reasoning trail | FinRL-Trading | L1 | Low (~45 lines) | 🔴 High | 1 |
| 4 | Link evidence back to hypothesis | Vibe-Trading | L5 | Medium (~40 lines) | 🟠 Med-High | 2 |
| 5 | Stock characterization before loop | FinRL-Trading | L2 | Medium (~60 lines) | 🟠 Med-High | 2 |
| 6 | Rolling strategy update | Qlib | L4 | Medium (~40 lines) | 🟠 Medium | 2 |
| 7 | Goal-driven criteria termination | Vibe-Trading | L7 | Medium (~65 lines) | 🟠 Medium | 3 |
| 8 | Turbulence risk overlay | FinRL-Meta | L4 | Low (~30 lines) | 🟡 Medium | 3 |
| 9 | Multi-agent swarm | Vibe-Trading | L6 | High (~80 lines) | 🟡 Medium | 3 |
| 10 | Multi-stage decision pipeline | FinRL-Trading | L2 | High (~100 lines) | 🟡 Medium | 4 |

---

## Recommended Next Steps

1. **Add `inject_past_run_summary()` to `llm_generator.py`** — simplest change,
   highest impact. ~20 lines. Query past 5 runs from SQLite, summarize, inject
   into LLM prompt.

2. **Add reasoning trail to `IterationRecord`** — ~15 lines in `models.py`.
   Capture the LLM's reasoning at each iteration for post-mortem diagnosis.

3. **Extend `hypothesis_registry.py`** with lifecycle states and evidence tracking
   (~60 lines). This is the foundation for all higher cognitive layers.

---

## Appendix: Repo Directories

```
/personal-important/other-reference-repos/
├── new_repos_and_some_understanding.md     # Existing blueprint (data/execution focus)
├── ref-qlib/                               # Microsoft Qlib — feature engine + ML
├── ref-FinRL-Meta/                         # FinRL — simulation environment
├── ref-FinRL-Trading/                      # FinRL — live trading execution
├── ref-FinRobot/                           # FinRobot — multi-agent news analysis
└── Vibe-Trading/                           # HKUDS Vibe-Trading — LLM trading agent
```
