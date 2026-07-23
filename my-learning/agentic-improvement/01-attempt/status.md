# Memory-First Agent — Status Tracker

**Total:** 4 | **Completed:** 4 | **In Progress:** 0 | **Pending:** 0

> Update this file after completing each phase — mark `Completed` and add the date.

---

## Phases

| ID | Title | Lines | Dependencies | Status | Date Fixed | Notes |
|----|-------|-------|-------------|--------|------------|-------|
| P1 | Memory Injection | ~65 | None | Completed | 2026-07-23 | Query past runs, inject into LLM prompts, store reasoning |
| P2 | Self-Awareness | ~120 | Phase 1 | Completed | 2026-07-23 | Stock characterization, 0-trade diagnosis, audit trail |
| P3 | Hypothesis Brain | ~130 | Phases 1+2 | Completed | 2026-07-23 | Evidence lifecycle, hypothesis registry upgrade |
| P4 | Meta-Intelligence | ~150 | All phases | Completed | 2026-07-23 | Adaptive critic, meta-reflection, goal validation, rolling updates |

---

## Detailed Phase Tasks

### P1 — Memory Injection ✅ Completed 2026-07-23

| Task | File | Lines | Status |
|------|------|-------|--------|
| Add `get_past_run_summaries()` | `storage/sqlite_backend.py` | ~12 | Completed |
| Add `_build_memory_context()` | `llm_generator.py` | ~10 | Completed |
| Inject memory into generation prompt | `llm_generator.py` | ~10 | Completed |
| Inject memory into refinement prompt | `llm_generator.py` | ~5 | Completed |
| Add `reasoning` field to `IterationRecord` | `models.py` | ~1 | Completed |
| Store memory context on loop | `loop.py` | ~5 | Completed |
| Include memory in story dict for LLM | `loop.py` | ~8 | Completed |
| Capture LLM reasoning in quant coder | `loop.py` | ~2 | Completed |
| Set reasoning on IterationRecord | `loop.py` | ~2 | Completed |
| Build memory context in service | `service.py` | ~10 | Completed |
| Pass memory_context to loop.run() | `service.py` | ~1 | Completed |

### P2 — Self-Awareness ✅ Completed 2026-07-23

| Task | File | Lines | Status |
|------|------|-------|--------|
| Add `_diagnose_failure()` for 0-trade | `loop.py` | ~15 | Completed |
| Add diagnosis call after backtest | `loop.py` | ~10 | Completed |
| Add `_characterize_stock()` method | `loop.py` | ~35 | Completed |
| Wire characterization before loop | `loop.py` | ~1 | Completed |
| Add diagnosis prompt template | `llm.py` | ~30 | Completed |
| Add `DecisionRecord` dataclass | `models.py` | ~15 | Completed |
| Pass stock profile through story dict | `loop.py` + `llm_generator.py` | ~15 | Completed |
| Add stock profile to generation/refinement prompts | `llm_generator.py` | ~10 | Completed |
| Add stock characterization LLM method | `llm.py` | ~15 | Completed |

### P3 — Hypothesis Brain ✅ Completed 2026-07-23

| Task | File | Lines | Status |
|------|------|-------|--------|
| Add `Evidence` dataclass | `models.py` | ~10 | Completed |
| Extend `Hypothesis` with new fields | `models.py` | ~10 | Completed |
| Update `_to_dict`/`_from_dict` for new fields | `hypothesis_registry.py` | ~40 | Completed |
| Add `add_evidence()` to registry | `hypothesis_registry.py` | ~20 | Completed |
| Add `reject_with_reason()` | `hypothesis_registry.py` | ~15 | Completed |
| Add `query_by_symbol()` | `hypothesis_registry.py` | ~12 | Completed |
| Wire hypothesis query at start of loop | `loop.py` | ~20 | Completed |
| Wire evidence update after loop | `loop.py` | ~20 | Completed |
| Pass hypothesis registry to loop | `service.py` | ~3 | Completed |
| Merge hypothesis evidence into memory_context | `loop.py` | ~15 | Completed |

### P4 — Meta-Intelligence ✅ Completed 2026-07-23

| Task | File | Lines | Status |
|------|------|-------|--------|
| Add adaptive critic suggestion tracking | `loop.py` | ~8 | Completed |
| Add `_filter_ineffective_suggestions()` | `loop.py` | ~12 | Completed |
| Apply filter in template fallback path | `loop.py` | ~1 | Completed |
| Add `_reflect()` meta-strategy method | `loop.py` | ~20 | Completed |
| Wire reflection after iteration 2 | `loop.py` | ~15 | Completed |
| Add `_validate_idea()` goal check | `loop.py` | ~15 | Completed |
| Wire goal validation before loop | `loop.py` | ~8 | Completed |
| Add reflection prompt + LLM method | `llm.py` | ~20 | Completed |
| Add validation prompt + LLM method | `llm.py` | ~20 | Completed |
| Add `refresh_strategy()` rolling update | `service.py` | ~35 | Completed |

---

## Files Changed Summary

| File | P1 | P2 | P3 | P4 | Total |
|------|-----|-----|-----|-----|-------|
| `storage/sqlite_backend.py` | ✅ ~12 | — | — | — | ~12 |
| `llm_generator.py` | ✅ ~27 | ✅ ~10 | — | — | ~37 |
| `models.py` | ✅ ~1 | ✅ ~15 | ✅ ~20 | — | ~36 |
| `llm.py` | — | ✅ ~45 | — | ✅ ~40 | ~85 |
| `loop.py` | ✅ ~15 | ✅ ~60 | ✅ ~55 | ✅ ~60 | ~190 |
| `service.py` | ✅ ~10 | — | ✅ ~3 | ✅ ~35 | ~48 |
| `hypothesis_registry.py` | — | — | ✅ ~90 | — | ~90 |

---

## Summary

| Status | Count |
|--------|-------|
| ✅ Completed | 4 |
| 🔄 In Progress | 0 |
| ⏳ Pending | 0 |
| **Total** | **4** |
