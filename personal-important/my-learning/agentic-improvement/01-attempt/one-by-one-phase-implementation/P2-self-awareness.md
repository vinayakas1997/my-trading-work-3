# P2 — Self-Awareness

**Phase:** 2
**Total Lines:** ~120
**Dependencies:** Phase 1 (Memory Injection)
**Status:** ✅ Completed 2026-07-23

---

## What Was Built

The agent diagnoses root causes of failures (especially 0-trade results) and characterizes each stock's behavior before writing any strategy code.

### Files Changed

| File | Change | Lines |
|------|--------|-------|
| `models.py` | Added `DecisionRecord` dataclass for full reasoning trail | ~15 |
| `llm.py` | Added `DIAGNOSIS_SYSTEM_PROMPT`, `STOCK_CHARACTERIZATION_PROMPT`, `_build_diagnosis_prompt()`, `_build_characterization_prompt()` | ~30 |
| `llm.py` | Added `diagnose_failure()`, `characterize_stock()`, `suggest_pivot()`, `validate_idea()` methods to `ResearchLlmClient` | ~15 |
| `llm_generator.py` | Added `stock_profile` parameter through all prompt builders and generate/refine chain | ~10 |
| `loop.py` | Added `_characterize_stock()` — builds profile from angle context + feature snapshot, optionally LLM-enriched | ~35 |
| `loop.py` | Added `_diagnose_failure()` — calls LLM when `trade_count == 0` to analyze root cause | ~15 |
| `loop.py` | Wired stock characterization before the loop, diagnosis after 0-trade backtests | ~10 |

### Data Flow

```
New run for JPM starts
    │
    ▼
_characterize_stock()
    │ angle_context: trend lifecycle, regime
    │ feature_snapshot: RSI, ADX, ATR values
    │ LLM enriches: "JPM is strongly trending, avoid mean-reversion"
    │ stores on self._stock_profile
    │ merges into story dict for LLM prompts
    │
    ▼
LLM generates code with stock profile context
    │ "I'll use SMA crossover momentum because JPM trends"
    │
    ▼
Backtest: 0 trades → _diagnose_failure()
    │ "SMA 50/200 never triggered — price too tight"
    │ stored in IterationRecord.reasoning
    │
    ▼
record.reasoning now contains the LLM diagnosis
```

### Impact

| Metric | Before | After |
|--------|--------|-------|
| 0-trade failures | Blind retry | Root cause identified and avoided |
| Strategy choice | Random/guessed | Data-driven based on stock profile |
| Debugging | "Sharpe was 0" | "RSI range 35-65, never hit 30/70 threshold" |
| Learning rate | Same mistakes iter after iter | Each iteration informed by diagnosis |
