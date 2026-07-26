# Phase 13 — Judgment Quality & Cost Realism

## Changes

### Provider Pricing (`vinu-lib/llm/providers.py`)
- Added `pricing: dict[str, dict[str, float]]` field to `ProviderCapabilities` — maps model name → `{"input_per_1m": ..., "output_per_1m": ...}`
- `get_model_pricing(model)` — returns pricing for a specific model, falls back to `"default"` key
- `estimate_cost(model, prompt_tokens, completion_tokens)` — computes USD cost from token counts and model pricing

### Cost Tracker (`vinu-lib/llm/cost.py`)
- `TokenUsage` dataclass — `prompt_tokens`, `completion_tokens`, `total_tokens`; `from_api_response(data)` extracts from OpenAI-style response dict
- `CostEntry` dataclass — captures single LLM call metadata (service, model, provider, token counts, cost, duration, success)
- `CostTracker` — thread-safe accumulator with `record()`, `summary()`, `reset()`, property accessors
- `get_global_cost_tracker()` — module-level singleton

### Token Tracking in LLM Clients (`client.py`, `client_async.py`)
- `_log_llm_call` updated to accept optional `token_usage: TokenUsage` and `estimated_cost: float` — serialized into JSON log entry
- Both sync and async `_chat_request` now extract `TokenUsage.from_api_response(data)`, compute cost via `caps.estimate_cost()`, pass to logging **and** record in global `CostTracker`

### Goal Budget Wiring (`loop.py`, `service.py`)
- `Goal` import added to loop.py
- `loop.run()` accepts optional `goal: Goal` parameter
- `_check_goal_budget(iteration)` — checks `llm_calls_budget` and `time_budget_seconds` against running counters; returns True to stop the loop
- `_track_goal_llm_call()` — increments counter after each LLM call site
- Tracked LLM call sites: `_quant_coder` generation, `_risk_critic` evaluation, `_diagnose_failure`, `_reflect()`
- `_goal.llm_calls_used` and `_goal.time_used_seconds` updated on each check

### Judgment Store (`vinu-research/vinu_research/judgment_store.py`)
- `JudgmentRecord` dataclass — captures verdict, in-sample/out-of-sample/holdout Sharpe, correctness, LLM calls used
- `JudgmentStore` — thread-safe, optionally persists to JSONL file
- `calibration_summary()` — returns accuracy breakdown by verdict category

## Test Results
- `test_cost.py` (vinu-lib): 9 tests — TokenUsage parsing, CostTracker record/summary/totals/reset/calls-by-model, global singleton
- `test_providers.py` (vinu-lib): 6 tests — empty pricing, model-specific, fallback to default, cost estimation, zero tokens, no pricing
- `test_judgment_store.py` (research): 6 tests — record/count, calibration summary, persistence/load, reset
- **All 21 new tests pass.** Full vinu-lib suite: 58/58 pass. Full research suite: 422/429 pass (7 pre-existing Windows/PermissionError failures excluded).
