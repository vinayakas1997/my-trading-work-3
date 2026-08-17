---
name: llm-provider-fallback
closes: shortcoming #9 in ../01-vinu-components-shortcomings.md
ports: provider-waterfall pattern, per ../02-reference-repos-core-logic.md
status: done — gap confirmed to exist and a waterfall was added
---

# Task: confirm and, if missing, add an LLM provider fallback

## Goal

Determine whether the Planner and Researcher/Executor currently have any fallback if their primary LLM
provider is unavailable, and if not, add a simple waterfall.

## Why

This was flagged as **unconfirmed** in the shortcomings audit — the original exploration didn't directly
check for provider-fallback logic. Do the confirmation step first; don't assume the gap exists.

## Current state (verified 2026-08-17 — this item was NOT directly audited, confirm from scratch)

- Reference pattern to port if needed: `jarvis-trading-bot/jarvis_agents.py`'s `_call_llm()` — a manual
  provider waterfall (Groq → Gemini → OpenRouter/DeepSeek), each vendor's SDK/HTTP called directly, no
  framework. Simple and effective for what it does.
- Where to look in this codebase: whatever module handles the actual model call for agent teams —
  likely `core/model_router.py`-equivalent or `core/providers.py`-equivalent under `vinu-agent` or
  `vinu-research`. Not yet located during this audit pass — first step below is finding it.

## Steps

1. Locate the actual LLM-calling code path used by the Planner and Researcher/Executor teams (grep for
   the model-calling library/SDK in use across `vinu-agent`/`vinu-research`).
2. Determine: is there already a fallback (different provider, or same provider with retry) if the
   primary call fails or times out? If yes — this task is done, just document what exists and close it
   out; no need to build anything.
3. If no fallback exists: read `jarvis-trading-bot/jarvis_agents.py`'s `_call_llm()` for the pattern, and
   implement an equivalent waterfall using whichever providers this project already has API keys/access
   for (don't assume Groq/Gemini/OpenRouter specifically — match whatever this project's existing model
   router already supports).
4. Make sure a fallback triggers on genuine failure/timeout, not on a normal slow-but-successful response
   — don't want to double-call a provider that's just being slow.
5. Log which provider actually served each call, so a pattern of frequent fallback (indicating a primary
   provider is degraded) is visible/traceable, consistent with this project's traceability discipline.

## Acceptance criteria

- A clear yes/no answer, with evidence, on whether this gap actually existed before any code was written.
- If a fallback was added: a test that simulates the primary provider failing and confirms the call
  still succeeds via the fallback provider.
- If no fallback was needed: this file is updated to say so, with the file:line evidence for what already
  handles it, so it's not re-investigated later.

## Dependencies

None.
