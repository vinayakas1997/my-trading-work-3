# S-09: Anti-Hallucination Guardrails — Explanation & Status

## What It Is

Injects a single instruction into four research prompts to prevent the LLM from fabricating numerical data not present in the provided context.

## Components

1. **Prompt injection** — the instruction `"Only cite specific numbers that appear in the data provided above"` was added to the system/user prompt of four prompts in `vinu_research/llm.py`:
   - `DIAGNOSIS_SYSTEM_PROMPT`
   - `STOCK_CHARACTERIZATION_PROMPT`
   - `REFLECTION_SYSTEM_PROMPT`
   - `VALIDATION_SYSTEM_PROMPT`

2. **Scope** — coverage includes the diagnosis, characterization, reflection, and validation stages. The instruction appears near the end of each prompt to act as a final reminder before the LLM generates its response.

## Current Status: ✅ IMPLEMENTED

All four research prompts include the numerical citation guardrail.
