# Task 3: Pass Cross-Run Context to LLM Prompt

**Status:** DONE

## Purpose

Give the LLM risk critic visibility into the symbol's lifetime history so it can make more informed verdict decisions. Without this context, the LLM judges each iteration in isolation — it doesn't know that this is the 20th attempt on the same symbol.

## Approach

1. Added optional `catalog_entry` parameter to `_llm_enhanced_check()`
2. Added optional `catalog_entry` parameter to `_build_risk_critic_prompt()`
3. When `catalog_entry` is provided, insert a "Cross-Run History" section in the prompt showing `lifetime_trial_count` and `best_sharpe_ever`
4. Existing callers unaffected — parameter defaults to `None`

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu-research/vinu_research/llm.py` | 32-59 | Added `catalog_entry` param to `_build_risk_critic_prompt`; added Cross-Run History section |
| `vinu-research/vinu_research/loop.py` | 1448-1466 | Added `catalog_entry` param to `_llm_enhanced_check`; passes it to prompt builder |

## Verification

- [x] 407/407 research tests pass
