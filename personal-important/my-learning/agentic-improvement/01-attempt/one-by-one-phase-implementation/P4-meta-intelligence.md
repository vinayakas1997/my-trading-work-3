# P4 — Meta-Intelligence

**Phase:** 4
**Total Lines:** ~150
**Dependencies:** All phases
**Status:** ✅ Completed 2026-07-23

---

## What Was Built

The agent pivots when stuck, learns which critic suggestions work, validates user ideas before starting, and tries incremental strategy refresh before full re-research.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `llm.py` | Added `REFLECTION_SYSTEM_PROMPT`, `VALIDATION_SYSTEM_PROMPT`. Added `suggest_pivot()` — decides continue/pivot/stop. Added `validate_idea()` — checks if user's idea fits stock behavior. | ~40 |
| `loop.py` | Added `_suggestion_results` dict tracking suggestion→[outcomes]. Added `_filter_ineffective_suggestions()` — removes suggestions that never improved Sharpe. Added `_reflect()` — after iteration 2, if all failed, LLM decides pivot/stop. Added `_validate_idea()` — before loop, checks stock profile vs user idea. Wired reflection + pivot break into iteration loop. Applied suggestion filter in `_generate_filters`. | ~60 |
| `service.py` | Added `refresh_strategy()` — when decay detected, tries incremental refinement first, falls back to full re-research. | ~35 |

### Data Flow

```
User: "mean-reversion for JPM"
    │
    ▼
_validate_idea()
    │ "JPM has AR1=0.95 (trending). Mean-reversion may not work.
    │  Suggested alternative: momentum"
    │ → Logs warning but doesn't block (user may override)
    │
    ▼
Iterations 1-2 fail with 0 trades
    │ Each iteration tracks suggestions:
    │   "add ADX filter" → applied → no improvement → marked INEFFECTIVE
    │   "widen RSI" → applied → slight improvement → marked EFFECTIVE
    │
    ▼
_reflect() after iteration 2
    │ "RSI never triggers. Pivot to momentum?"
    │ Decision: pivot
    │ → breaks from loop, next run uses different approach
    │
    ▼
refresh_strategy() (on decay)
    │ Tries incremental refinement first
    │ Falls back to full re-research only if needed
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Dead-end approaches | Wasted all iterations | Pivots after 2 failures |
| Critic suggestions | Same rules every time | Learns what works per stock |
| Impossible requests | Blindly attempted | Validated before starting |
| Strategy decay | Always full re-research | Incremental refresh attempted first |
