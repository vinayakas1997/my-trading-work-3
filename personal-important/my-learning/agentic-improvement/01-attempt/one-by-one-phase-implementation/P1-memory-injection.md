# P1 — Memory Injection

**Phase:** 1
**Total Lines:** ~65
**Dependencies:** None (standalone)
**Status:** ✅ Completed 2026-07-23

---

## What Was Built

The agent remembers past runs for the same symbol and uses that memory to avoid repeating failures. Also stores the LLM's reasoning at each iteration for debugging.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `storage/sqlite_backend.py` | Added `get_past_run_summaries(symbol, limit)` — returns compact summaries of past runs | ~12 |
| `llm_generator.py` | Added `_build_memory_context()` — builds human-readable string from past summaries. Modified `_build_generation_prompt()`, `_build_refinement_prompt()`, `generate()`, `_generate_one()`, `refine()`, `_refine_one()` to accept and pass `memory_context`. Memory is carried through the `story` dict. | ~27 |
| `models.py` | Added `reasoning: str = ""` field to `IterationRecord` | ~1 |
| `loop.py` | Added `memory_context` param to `run()`. Stores on `self._memory_context`. `_default_quant_coder()` includes it in the `story` dict so LLM sees it. Captures `self._last_reasoning` from ranked candidates. Sets `record.reasoning` on each `IterationRecord`. | ~15 |
| `service.py` | After inserting the run record, queries `get_past_run_summaries()` for the symbol, builds memory context with `_build_memory_context()`, passes it to `loop.run()`. | ~10 |

### Data Flow

```
User: "mean-reversion for JPM"
    │
    ▼
service.py: query SQLite for past runs of JPM
    │ Returns: Run#42: mean-rev→0.00, Run#44: SMA cross→0.30,
    │          Run#45: Bollinger→0.80 (ACTIVE)
    ▼
service.py: build memory context string
    │ "Past research on JPM:
    │  Run#42: mean-reversion → Sharpe 0.00
    │  Run#44: SMA crossover → Sharpe 0.30
    │  Run#45: Bollinger Bands → Sharpe 0.80 (ACTIVE)"
    ▼
loop.run() receives memory_context
    │ stores on self._memory_context
    ▼
_default_quant_coder() builds story dict
    │ story = {angles: ..., features: ..., memory_context: "..."}
    ▼
LlmStrategyGenerator.generate() extracts memory_context from story
    │ → _generate_one() → _build_generation_prompt(memory_context=...)
    │ LLM sees past run history in its prompt
    ▼
LLM generates strategy avoiding past failures
    │ "Let me try SMA crossover since Bollinger is already active
    │  and mean-reversion failed 3 times"
    ▼
self._last_reasoning = best.reasoning
    ▼
IterationRecord created with reasoning
    │ record.reasoning = "Avoiding mean-rev because past 3 runs failed"
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| Repeated failures | Every new run repeats past mistakes | LLM sees and avoids past failures |
| Debug visibility | Only see final metrics | Each iteration has LLM reasoning |
| Cross-session learning | Zero | Last 5 runs inform every new run |
| User experience | "Why is it trying the same thing again?" | "It remembered what failed last time" |

### Verification

1. Run research on a symbol that has past runs (e.g., JPM with mean-reversion history)
2. Check the LLM generation prompt for the memory context string
3. Verify the generated strategy avoids approaches that failed in past runs
4. Check `IterationRecord.reasoning` is populated in the ResearchResult
