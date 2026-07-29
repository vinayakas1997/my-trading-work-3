# Memory-First Agent — Complete Implementation Plan

> A trading system that learns from experience, diagnoses its own failures, and comes to understand each stock like an expert would — before risking real money.

---

## Architecture Overview — How Everything Connects

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    YOUR EXISTING SYSTEM (what you have)                      │
│                                                                             │
│  INITIAL-ANALYSIS (deterministic)  ──→  RESEARCH-SIMULATIONS (LLM-driven)  │
│  ┌──────────────────────┐            ┌──────────────────────────┐          │
│  │ 19 angles computed   │            │ loop.py iteration loop    │          │
│  │ Trend lifecycle      │──context──→│ Generate → Backtest →     │          │
│  │ RSI distribution     │            │ Critic → PASS/REFINE/STOP │          │
│  │ Volatility profile   │            └──────────────────────────┘          │
│  └──────────────────────┘                      │                            │
│                                                ▼                            │
│                                    ┌──────────────────────┐                │
│                                    │  SQLite (saves)       │                │
│                                    │  research_runs table   │                │
│                                    │  strategy_store table  │                │
│                                    └──────────────────────┘                │
│                                                                             │
│  THE GAP: These pieces don't talk to each other. Saves everything,         │
│  reads nothing back before starting a new run.                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                    WHAT WE'RE BUILDING (4 phases)                            │
│                                                                             │
│  Phase 1: Memory Injection ──── "Don't repeat past failures"               │
│  Phase 2: Self-Awareness ────── "Know why you failed"                       │
│  Phase 3: Hypothesis Brain ──── "Learn what works for each stock"          │
│  Phase 4: Meta-Intelligence ─── "Pivot when stuck, seek info"              │
│                                                                             │
│  Each phase builds on the previous. Phase 1 is standalone.                  │
│  Phase 2 needs Phase 1. Phase 3 needs Phases 1+2. Phase 4 needs all.       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Document Coverage

| Document | Covered In |
|----------|-----------|
| `00-vision.md` §1 (3-Environment Architecture) | All phases — LLM stays in Research-Simulations only |
| `00-vision.md` §2 (Stateless Loop Problem) | Phase 1 — memory injection |
| `00-vision.md` §3 (Memory-First Agent) | Phases 1-3 — memory at every layer |
| `00-vision.md` §4 (7 Cognitive Layers) | Phase 1: L3, Phase 2: L1+L2, Phase 3: L3+L7, Phase 4: L4+L5+L6+L7 |
| `00-vision.md` §5 (Hypothesis Registry) | Phase 3 — full lifecycle with evidence |
| `00-vision.md` §6 (Reference Repo Patterns) | Phase 1: Vibe-Trading Pattern 1C, Phase 2: FinRL Pattern 2A, Phase 3: Vibe-Trading 1A+1B, Phase 4: Qlib 3A + FinRL-Meta 4A |
| `00-vision.md` §7 (Implementation Roadmap) | Matches our 4 phases |
| `01-improvement.md` §1-7 (7 Gaps) | Gap 1→Phase 1, Gap 2→Phase 1, Gap 3→Phase 4, Gap 4→Phase 3, Gap 5→Phase 4, Gap 6→Phase 4, Gap 7→Phase 4 |
| `02-cognitive-layers.md` L1-L7 | L1→Phase 2, L2→Phase 2, L3→Phase 1+3, L4→Phase 4, L5→Phase 4, L6→Phase 4, L7→Phase 4 |
| `03-reference-patterns.md` 10 Patterns | All 10 patterns mapped to specific phases above |

---

## PHASE 1: Memory Injection (~63 lines)

**Source:** `00-vision.md §2-3`, `01-improvement.md §1-2`, `03-reference-patterns.md Pattern 1C`

**Goal:** The agent remembers past runs and stops repeating failures.

### What Changes

| File | Change | Lines |
|------|--------|-------|
| `storage/sqlite_backend.py` | Add `get_past_run_summaries()` method | ~12 |
| `llm_generator.py` | Add `_build_memory_context()` function, modify prompt builders | ~25 |
| `models.py` | Add `reasoning` field to `IterationRecord` | ~1 |
| `loop.py` | Query past runs before loop, pass memory context, store reasoning | ~20 |
| `service.py` | Pass `storage` reference to loop | ~5 |

### Data Flow

```
User: "mean-reversion for JPM"
    │
    ▼
Query SQLite for past runs of JPM
    │ Returns: Run#42: mean-rev→0.00, Run#44: SMA cross→0.30,
    │          Run#45: Bollinger→0.80 (ACTIVE)
    ▼
Build memory context string
    │ "Past research on JPM:
    │  Run#42: mean-reversion → Sharpe 0.00
    │  Run#44: SMA crossover → Sharpe 0.30
    │  Run#45: Bollinger Bands → Sharpe 0.80 (ACTIVE)"
    ▼
Inject into LLM generation prompt
    │ LLM now knows mean-rev failed → generates momentum instead
    ▼
Store LLM's reasoning in IterationRecord
    │ "Avoiding mean-rev because past 3 runs failed"
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Repeated failures | Every new run repeats past mistakes | LLM sees and avoids past failures |
| Debug visibility | Only see final metrics | Each iteration has LLM reasoning |
| Cross-session learning | Zero | Last 5 runs inform every new run |
| User experience | "Why is it trying the same thing again?" | "It remembered what failed last time" |

---

## PHASE 2: Self-Awareness (~100 lines)

**Source:** `00-vision.md §4 Layers 1-2`, `02-cognitive-layers.md §L1-L2`, `03-reference-patterns.md Pattern 2A`

**Goal:** The agent diagnoses why it fails and understands the stock before writing code.

### What Changes

| File | Change | Lines |
|------|--------|-------|
| `loop.py` | Add `_diagnose_failure()` method for 0-trade analysis | ~25 |
| `loop.py` | Add `characterize_stock()` step before iteration loop | ~30 |
| `llm.py` | Add diagnosis prompt template | ~20 |
| `models.py` | Add `DecisionRecord` dataclass for full reasoning trail | ~15 |
| `llm_generator.py` | Pass stock profile to prompt builders | ~10 |

### Data Flow

```
New run for JPM starts
    │
    ▼
Stock Characterization (Layer 2)
    │ Fetch volatility, RSI distribution, AR(1), ADX
    │ LLM analyzes: "JPM trends strongly, RSI never extreme"
    ▼
Memory from Phase 1 (Layer 3)
    │ "Past runs: mean-rev failed 3x"
    ▼
LLM generates code
    │ "I'll use SMA crossover momentum because JPM trends
    │  and RSI doesn't hit extremes"
    ▼
Backtest: 0 trades → WHY?
    ▼
Self-Diagnosis (Layer 1)
    │ "SMA 50/200 crossover never triggered because price stayed
    │  between 148-155 (too narrow for 50/200 cross)"
    ▼
Critic now has: diagnosis + memory + stock profile
    → suggests: "Use shorter SMA 10/30 or switch to breakout"
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| 0-trade failures | Blind retry | Root cause identified and avoided |
| Strategy choice | Random/guessed | Data-driven based on stock profile |
| Debugging | "Sharpe was 0" | "RSI range 35-65, never hit 30/70 threshold" |
| Learning rate | Same mistakes iter after iter | Each iteration informed by diagnosis |

---

## PHASE 3: Hypothesis Brain (~110 lines)

**Source:** `00-vision.md §5`, `02-cognitive-layers.md §L3`, `03-reference-patterns.md Patterns 1A-1B`

**Goal:** The hypothesis registry becomes a true learning memory with lifecycle, evidence, and structured knowledge.

### What Changes

| File | Change | Lines |
|------|--------|-------|
| `models.py` | Add `Evidence` dataclass, extend `Hypothesis` with fields | ~20 |
| `hypothesis_registry.py` | Add `add_evidence()`, `reject_with_reason()`, `query_by_symbol()` | ~35 |
| `loop.py` | Wire hypothesis query at start, evidence update at end | ~30 |
| `service.py` | Pass hypothesis registry to loop | ~10 |
| `llm_generator.py` | Inject hypothesis evidence into prompts | ~15 |

### Data Flow

```
New run: "momentum for JPM"
    │
    ▼
Hypothesis Registry Query (Layer 3 + Layer 7)
    │ "Any active hypothesis for JPM?"
    │
    ├── YES: "JPM-momentum-SMA" (VALIDATED, Sharpe 0.82)
    │   → Inject evidence into prompt
    │   → "SMA 50/200 works for JPM"
    │
    └── NO: Create new hypothesis → status: EXPLORING
    │
    ▼
3 iterations run
    │ Iter 1: Sharpe 0.35, Iter 2: Sharpe 0.60, Iter 3: Sharpe 0.82
    │
    ▼
Update Hypothesis
    │ Add 3 evidence records
    │ best_sharpe: 0.82
    │ status: VALIDATED
    │ indicators: [sma_50, sma_200]
    │
    ▼
NEXT RUN for JPM:
    "Past validated: SMA 50/200 momentum (Sharpe 0.82).
     Try refinement or different indicator class."
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Knowledge per stock | None (stateless) | Structured evidence per hypothesis |
| Cross-session learning | Last 5 runs only | Full history with evidence + reasons |
| Rejected approaches | Repeated blindly | Rejected with documented WHY |
| Strategy validation | Single-run snapshot | Evidence-backed lifecycle |

---

## PHASE 4: Meta-Intelligence (~170 lines)

**Source:** `00-vision.md §4 Layers 4-7`, `02-cognitive-layers.md §L4-L7`, `03-reference-patterns.md Patterns 1B, 3A, 4A`

**Goal:** The agent pivots when stuck, learns which suggestions work, seeks information, and validates user ideas.

### What Changes

| File | Change | Lines |
|------|--------|-------|
| `loop.py` | Add `_reflect()` meta-strategy, `_validate_idea()`, adaptive critic filter | ~50 |
| `llm_generator.py` | Add tool definitions, function-calling integration | ~60 |
| `service.py` | Add `refresh_strategy()` for rolling updates | ~35 |
| `llm.py` | Add reflection + validation prompt templates | ~25 |

### Data Flow

```
User: "mean-reversion for JPM"
    │
    ▼
L7: Goal Validation
    │ "JPM has AR1=0.95 (trending). Mean-reversion will likely fail.
    │  Suggest momentum instead."
    │
    ▼
Iterations 1-2 fail
    │ Sharpe 0.00, 0 trades
    │
    ▼
L5: Meta-Reflection
    │ "RSI never triggers on JPM. Pivot to momentum?"
    │ Decision: PIVOT
    │
    ▼
Iterations 3-5: momentum
    │ LLM generates SMA crossover
    │ Sharpe improves: 0.00 → 0.35 → 0.60 → 0.82
    │
    ▼
L4: Adaptive Critic
    │ "ADX filter didn't help. Don't suggest it again."
    │ "Wider RSI thresholds helped. Suggest earlier."
    │
    ▼
Hypothesis: VALIDATED
    │ SMA 50/200 momentum for JPM
    │ Evidence: 3 supporting records, Best Sharpe: 0.82
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Dead-end approaches | Wasted all iterations | Pivots after 2 failures |
| Critic suggestions | Same rules every time | Learns what works per stock |
| Impossible requests | Blindly attempted | Validated before starting |
| Strategy decay | Full re-research | Incremental refresh attempted first |
| LLM information | Limited to pre-computed | Can query data on demand |

---

## Complete Summary

### Total Effort

| Phase | Lines | Time | Dependencies | Impact |
|-------|-------|------|-------------|--------|
| Phase 1: Memory Injection | ~63 | 1 week | None (standalone) | "It stops repeating itself" |
| Phase 2: Self-Awareness | ~100 | 1 week | Phase 1 | "It knows why it failed" |
| Phase 3: Hypothesis Brain | ~110 | 1-2 weeks | Phases 1+2 | "It learns what works per stock" |
| Phase 4: Meta-Intelligence | ~170 | 1-2 weeks | All phases | "It thinks before acting" |
| **Total** | **~443** | **4-6 weeks** | — | — |

### Files Changed Across All Phases

| File | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Total |
|------|---------|---------|---------|---------|-------|
| `loop.py` | ~20 | ~55 | ~30 | ~50 | ~155 |
| `llm_generator.py` | ~25 | ~10 | ~15 | ~60 | ~110 |
| `models.py` | ~1 | ~15 | ~20 | — | ~36 |
| `llm.py` | — | ~20 | — | ~25 | ~45 |
| `hypothesis_registry.py` | — | — | ~35 | — | ~35 |
| `storage/sqlite_backend.py` | ~12 | — | — | — | ~12 |
| `service.py` | ~5 | — | ~10 | ~35 | ~50 |

### Impact Trajectory

```
Phase 1: "It stops repeating itself"          — Immediate user-visible improvement
Phase 2: "It knows why it failed"             — Debugging becomes 10x easier
Phase 3: "It learns what works per stock"     — Knowledge compounds across sessions
Phase 4: "It thinks before acting"            — True agentic intelligence
```

### How to Start

**Day 1:** Implement Phase 1 (memory injection). Smallest change with biggest immediate impact.

**After Phase 1:** Run 3-5 research sessions on different stocks. Observe how memory context changes LLM's strategy choices.

**Validation:** After each phase, test with a stock you've already researched (e.g., JPM if mean-reversion was tried before). The agent should reference past attempts and avoid repeating them.
