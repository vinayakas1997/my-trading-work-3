# DA-22 🟡 No Retry on Transient LLM Failure (All 6 LLM Clients)

**Component:** `vinu-infra`, `vinu-agent`
**Files Changed:** `client.py`, `client_async.py`, `agent/llm.py`

## Problem

**Zero retry logic on ANY LLM call across the entire codebase.** A single transient HTTP error (429 rate limit, 502 bad gateway, connection timeout) would silently return `None` or crash, depending on the component.

**15 call sites, 6 client implementations, 0 retry.**

Additionally, `LlmConfig.retry_max=3` was defined in `config.py` but **never read** by any client — dead code.

## Clients Fixed

| # | Client | File | Type | Fix |
|---|--------|------|------|-----|
| 1 | `LlmClient` (sync) | `vinu-infra/llm/client.py` | `requests` | Added inner retry loop around HTTP POST. Retries on `ConnectionError`, 429, 5xx, timeout. Exponential backoff: 1s → 2s → 4s (respects `retry_max` from config). Parse errors still return `None` immediately (permanent). |
| 2 | `AsyncLlmClient` (async) | `vinu-infra/llm/client_async.py` | `httpx` | Same retry loop, uses `await asyncio.sleep()`. Proper exception ordering: `ConnectError` → `HTTPStatusError` → `RequestError` → `HTTPError` → parse error. |
| 3 | `OpenAIChatLLM` | `vinu-agent/agent/llm.py` | `openai` SDK | Added `max_retries=3` + `timeout` to `OpenAI()` constructor. Wrapped `create()` in try/except → `RuntimeError`. |
| 4 | `DeepSeekChatLLM` | `vinu-agent/agent/llm.py` | `openai` SDK | Inherits from `OpenAIChatLLM` — fix applied automatically. |
| 5 | `AnthropicChatLLM` | `vinu-agent/agent/llm.py` | `anthropic` SDK | Added `max_retries=3` to `Anthropic()` constructor. Wrapped `messages.create()` in try/except → `RuntimeError`. |
| 6 | `OllamaChatLLM` | `vinu-agent/agent/llm.py` | raw `requests` | Full retry loop with exponential backoff. Retries on `ConnectionError`, `Timeout`, 429, 5xx. Raises `RuntimeError` after all attempts exhausted. |

## Autofixed Call Sites

Fixing the 2 shared clients in vinu-infra automatically fixes **10 of 15** call sites:

- **vinu-news** (3 sites): `client.py:37` (wrapper), `analyze.py:58` (analyze_article), `service.py:85` (worker loop) — all use `LlmClient` (sync)
- **vinu-research** (4 sites): `llm.py:163` (passthrough), `llm_generator.py:260`/`313`/`381` — all use `AsyncLlmClient` (async)
- **vinu-agent** (3 remaining): `loop.py:276`/`336`/`354` (`_call_llm`, `_auto_compact`, `_iterative_update`) — use the 4 custom clients fixed above

## Root Cause

The `LlmConfig` class in `vinu_infra/llm/config.py` has had `retry_max=3` defined since day one, but `LlmClient.chat_json()` and `AsyncLlmClient.chat_json()` never read it. The Docker hostname failover (`alternative_urls`) was the only resilience mechanism, and it only helps with loopback resolution, never with transient HTTP errors.

## Verification

All tests pass across all affected components:
- vinu-infra: 31 passed
- vinu-agent: 108 passed
- vinu-news: 2 passed (test_ticker_news_provider)
- vinu-research: 44 passed
