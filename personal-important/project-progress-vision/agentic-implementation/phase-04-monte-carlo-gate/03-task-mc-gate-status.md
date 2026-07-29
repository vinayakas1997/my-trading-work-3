# Task 3: Add `mc_gate_failed` to HypothesisStatus

**Status:** DONE

## Purpose

When a strategy fails the Monte Carlo validation gate, the hypothesis should record this terminal status so the registry and reports reflect why the strategy was abandoned.

## Approach

Add `mc_gate_failed = "mc_gate_failed"` to the `HypothesisStatus` enum.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/models.py` | 16 | Added `mc_gate_failed` enum value |

## Verification

- [x] 401/401 research tests pass
