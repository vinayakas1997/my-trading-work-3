# Memory-First Agent Implementation — Context & Process

## What We're Building

Implementing 4 phases to turn the stateless research loop into a memory-first agent that learns from experience, diagnoses failures, and becomes an expert on each stock over time.

### Phase Summary

| Phase | Title | Lines | Dependencies | Impact |
|-------|-------|-------|-------------|--------|
| P1 | Memory Injection | ~63 | None | "It stops repeating itself" |
| P2 | Self-Awareness | ~100 | Phase 1 | "It knows why it failed" |
| P3 | Hypothesis Brain | ~110 | Phases 1+2 | "It learns what works per stock" |
| P4 | Meta-Intelligence | ~170 | All phases | "It thinks before acting" |

### Components Modified

- `vinu-research` — loop.py, llm_generator.py, llm.py, models.py, service.py, hypothesis_registry.py
- `vinu-research/storage` — sqlite_backend.py

### Source Documents

All 4 vision/analysis documents in `my-learning/agentic-improvement/` are covered:
- `00-vision.md` — Architecture, memory-first agent, 7 cognitive layers
- `01-improvement.md` — 7 gaps in the current loop
- `02-cognitive-layers.md` — 7 cognitive layer implementations
- `03-reference-patterns.md` — 10 patterns from Vibe-Trading, FinRL, Qlib

---

## Status Tracking

All progress is tracked in **`status.md`** at the root of this directory. It contains a table of all 4 phases with task breakdown, status, and dates.

## Implementation Order

Phases must be implemented sequentially. Each phase depends on the previous.

### Phase 1 — Memory Injection ✅ Completed 2026-07-23

1. ✅ Add `get_past_run_summaries()` to `storage/sqlite_backend.py`
2. ✅ Add `_build_memory_context()` to `llm_generator.py`
3. ✅ Inject memory into `_build_generation_prompt()` and `_build_refinement_prompt()`
4. ✅ Add `reasoning` field to `IterationRecord` in `models.py`
5. ✅ Memory stored on `self` in loop, captured in story dict for LLM
6. ✅ In `service.py`: build memory context from past runs, pass to `loop.run()`

### Phase 2 — Self-Awareness ✅ Completed 2026-07-23

1. ✅ Add `_diagnose_failure()` to `loop.py` — LLM analyzes root cause of 0-trade failures
2. ✅ Add `_characterize_stock()` to `loop.py` — computes stock profile from angle context + features
3. ✅ Add diagnosis + characterization prompts in `llm.py`
4. ✅ Add `DecisionRecord` dataclass to `models.py`
5. ✅ Pass stock profile through story dict to prompt builders

### Phase 3 — Hypothesis Brain ✅ Completed 2026-07-23

1. ✅ Add `Evidence` dataclass and extend `Hypothesis` in `models.py`
2. ✅ Add `add_evidence()`, `reject_with_reason()`, `query_by_symbol()` to `hypothesis_registry.py`
3. ✅ Wire hypothesis query at start and evidence update at end in `loop.py`
4. ✅ Pass hypothesis registry to loop in `service.py`
5. ✅ Merge hypothesis evidence into memory_context for LLM prompts

### Phase 4 — Meta-Intelligence ✅ Completed 2026-07-23

1. ✅ Add adaptive critic suggestion tracking + `_filter_ineffective_suggestions()` in `loop.py`
2. ✅ Add `_reflect()` meta-strategy method + wiring in `loop.py`
3. ✅ Add `_validate_idea()` goal check + wiring in `loop.py`
4. ✅ Add `refresh_strategy()` rolling update in `service.py`
5. ✅ Add reflection + validation prompt templates + LLM methods in `llm.py`

---

## Documentation Format

After each phase, create a solution file in `one-by-one-phase-implementation/`:

```markdown
# P<N> <Title>

**Phase:** <N>
**Total Lines:** <N>
**Files Changed:** <file1>, <file2>

## What Was Built

Description of what was added.

## Data Flow

How data flows through the new code.

## Impact

Before/after metrics.

## Verification

How to confirm the phase works.
```

## Folder Structure

```
the-first-attempt/
├── AGENTS.md               ← This file
├── plan.md                 ← Full implementation plan
├── status.md               ← Phase/task status tracker
└── one-by-one-phase-implementation/
    ├── P1-memory-injection/
    ├── P2-self-awareness/
    ├── P3-hypothesis-brain/
    └── P4-meta-intelligence/
```
