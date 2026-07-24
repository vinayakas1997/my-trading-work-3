# Task 2: Wire Cross-Run Check into `_default_risk_critic`

**Status:** DONE

## Purpose

Integrate the cross-run comparison into the existing risk critic pipeline so it runs before the rule-based check and can short-circuit to STOP when lifetime evidence shows a dead-end symbol.

## Approach

Modified `_default_risk_critic` to:
1. Call `_cross_run_comparison()` first
2. If it returns a STOP verdict, return immediately without running rules or LLM
3. If it returns REFINE, merge its suggestions into the rules-based feedback
4. Pass `catalog_entry` to `_llm_enhanced_check` for richer context

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/loop.py` | 1548-1590 | Rewired `_default_risk_critic` to call `_cross_run_comparison` first, merge cross-run REFINE suggestions, and pass catalog_entry to LLM |

## Verification

- [x] 407/407 research tests pass
