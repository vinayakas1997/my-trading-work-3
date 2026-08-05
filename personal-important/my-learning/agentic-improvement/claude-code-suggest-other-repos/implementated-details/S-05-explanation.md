# S-05: JSONL Trace Writer — Explanation & Status

## What It Is

A research-layer tracing enrichment added to `vinu_research/llm.py`.

## Components

1. **`ResearchTraceWriter` class** — writes per-run JSONL traces to `{data_root}/traces/{run_id}.jsonl`. Each line is a structured JSON entry capturing a single LLM call during research.

2. **`set_trace_context(run_id, symbol)`** — sets up the tracing context on `ResearchLlmClient`, allowing subsequent `chat_json()` calls to annotate traces with the current run and symbol.

3. **`chat_json()` wrapper** — every call to `chat_json()` is now wrapped:
   - Captures latency (wall-clock time of the LLM round-trip)
   - Writes a structured trace entry with fields: `call_type`, `iteration`, `symbol`, `system_preview`, `user_preview`, `response_summary`, `success`, `error`

## Layering Note

The underlying infrastructure (`vinu_infra.llm.client_async._log_llm_call`) already writes a raw `llm_calls.jsonl` at the library level. The `ResearchTraceWriter` is a research-layer enrichment on top of that — it adds semantic context (symbol, iteration, call_type) that the raw log lacks.

## Current Status: ✅ IMPLEMENTED

Wired into `ResearchLlmClient.chat_json()` and active on all research runs.
