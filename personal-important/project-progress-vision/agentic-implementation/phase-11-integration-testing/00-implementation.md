# Phase 11: Integration Testing

**Status:** IN PROGRESS
**Started:** 2026-07-26
**Depends on:** Steps 1–10
**Blocks:** —

## What It Delivers

End-to-end integration tests covering the cross-component data flows built across Phases 7–10:

1. **Agent context + memory retrieval** — `ContextBuilder` with real `UnifiedMemoryStore`, verifying scored search, dedup, and context budget enforcement
2. **Catalog + exhaustion + loop** — `ResearchStorage` catalog exhaustion check wired into `StrategyResearchLoop.run()` early-exit
3. **Promotion + correlation gate** — `approve_run` flow with correlation gate blocking and BENCHING status

## Files Touched

| File | Service | Change Type |
|------|---------|-------------|
| `vinu-agent/tests/test_integration_context.py` | vinu-agent | create |
| `vinu-research/tests/test_integration_exhaustion.py` | vinu-research | create |
| `vinu-research/tests/test_integration_promotion.py` | vinu-research | create |

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | `test_integration_context.py` — ContextBuilder + UnifiedMemoryStore | DONE |
| 2 | `test_integration_exhaustion.py` — Catalog exhaustion + loop early-exit | DONE |
| 3 | `test_integration_promotion.py` — Approve + correlation gate + BENCHING | DONE |
