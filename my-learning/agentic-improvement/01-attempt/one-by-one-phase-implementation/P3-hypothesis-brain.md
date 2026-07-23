# P3 — Hypothesis Brain

**Phase:** 3
**Total Lines:** ~130
**Dependencies:** Phases 1+2
**Status:** ✅ Completed 2026-07-23

---

## What Was Built

The hypothesis registry becomes a true learning memory with lifecycle states, evidence tracking, and structured knowledge per stock. Every run contributes to a growing knowledge base.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `models.py` | Added `Evidence` dataclass. Extended `Hypothesis` with `strategy_type`, `indicators_used`, `params_tested`, `evidence`, `invalidation_reason`, `best_sharpe` | ~20 |
| `hypothesis_registry.py` | Updated `_to_dict()`/`_from_dict()` for new fields. Added `add_evidence()` — appends evidence, auto-updates status to validated/rejected. Added `reject_with_reason()` — sets REJECTED with reason. Added `query_by_symbol()` — gets all hypotheses for a symbol. | ~90 |
| `loop.py` | At run start: queries `query_by_symbol()` for existing hypothesis, creates one if none found. Merges hypothesis evidence into `memory_context` for LLM prompts. At run end: adds evidence from all iterations, rejects if all iterations failed. | ~55 |
| `service.py` | Creates `HypothesisRegistry` instance, passes to `StrategyResearchLoop` | ~3 |

### Data Flow

```
New run for JPM
    │
    ▼
query_by_symbol("JPM")
    │
    ├── Found: "JPM-momentum-SMA" (VALIDATED, Sharpe 0.82)
    │   → Inject evidence into memory_context
    │   → "Best Sharpe: 0.82, Iter 3: sharpe=0.82 → supports"
    │
    └── Not found: Create new hypothesis
        → status: EXPLORING
        → strategy_type: user_idea
        → universe: [JPM]
    │
    ▼
3 iterations run
    │
    ▼
Add evidence from each iteration
    │ Iter 1: sharpe=0.35, conclusion=contradicts
    │ Iter 2: sharpe=0.60, conclusion=supports
    │ Iter 3: sharpe=0.82, conclusion=supports
    │ Auto-status: validated → best_sharpe=0.82
    │
    ▼
NEXT RUN: Agent remembers validated hypothesis
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Knowledge per stock | None (stateless) | Structured evidence per hypothesis |
| Auto-validation | Manual | Auto-transitions based on Sharpe thresholds |
| Rejected approaches | Repeated blindly | Rejected with documented WHY |
