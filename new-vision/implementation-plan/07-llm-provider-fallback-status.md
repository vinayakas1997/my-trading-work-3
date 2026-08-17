---
task: 07-llm-provider-fallback.md
status: complete
---

# Status: task 07 — confirm and add an LLM provider fallback

## Did the gap exist before any code was written? YES — with evidence

The agent-teams LLM path (Planner, Researcher/Executor, risk_gatekeeper, etc.) is
`vinu-agent/vinu_agent/agent/llm.py`:

- `create_llm_from_config()` (llm.py:505 before the change) built **exactly one** provider from
  `LLMConfig` (`openai` / `deepseek` / `anthropic` / `ollama`) and returned it directly. No waterfall.
- Each concrete `ChatLLM` (OpenAIChatLLM, AnthropicChatLLM, OllamaChatLLM, DeepSeekChatLLM) retries the
  **same** provider with explicit backoff (`retry_max`), but there was no mechanism to move to a
  *different* provider when the primary was down/unauthorized/degraded.

So: same-provider retry existed; cross-provider fallback did not. That is the gap.

## What I did

- `vinu-agent/vinu_agent/config.py`
  - `LLMConfig` gains `fallbacks: "list[LLMConfig]"` — ordered list of full fallback provider configs
    for the same LLM slot.
  - `load_config()` parses `VINU_LLM_FALLBACKS` (a JSON array of `{provider, model_name, api_key,
    base_url, timeout, context_window}` objects) via `_load_llm_fallbacks()`; malformed JSON is a loud
    `ValueError`, not a silent no-op.
- `vinu-agent/vinu_agent/agent/llm.py`
  - New `FallbackChatLLM(ChatLLM)` — the waterfall: tries providers in order; falls to the next only
    when the current provider's `.chat()` **raises** (i.e. after that provider's own explicit
    retry/backoff is exhausted — a slow-but-successful response never triggers fallback). Successful
    results are tagged with `"provider"` (type/model) so call-logging shows who actually served the
    call; all-failed raises a `RuntimeError` naming every tried provider.
  - `create_llm_from_config()` wraps the primary plus each fallback into `FallbackChatLLM` when
    `fallbacks` is non-empty; unchanged (plain provider) otherwise.
  - `LoggingChatLLM._log()` now records the **serving** provider from `response["provider"]` when
    present, instead of always logging the outer wrapper's class name — so a frequent-fallback pattern
    is traceable in `llm_calls` rows.
- `vinu-agent/tests/test_llm_fallback.py` — NEW, 10 tests.

## What is achieved

- Planner and Researcher/Executor agent teams (both route through `create_llm`/`ChatLLM`) now fail over
  to a configured fallback provider when the primary genuinely fails, e.g.:
  `VINU_LLM_FALLBACKS='[{"provider":"deepseek","model_name":"deepseek-chat","api_key":"..."}]'`
- Fallback fires on failure/timeout only, never on a slow-but-successful response.
- Which provider served each call is visible in logs (`provider` tag + `LLM provider X failed … moving
  to next provider` warnings + `llm_calls` rows), per the traceability discipline.

## Testing

- `vinu-agent/tests/test_llm_fallback.py` (10 tests): primary failure → fallback serves with the
  serving-provider tag; primary success → fallback never called; all fail → error names every provider;
  single provider → no extra tag (backward compatible); slow-but-successful primary → fallback not
  fired; empty provider list rejected; `create_llm_from_config` builds a waterfall only when fallbacks
  configured; env parsing and malformed-env loudness.
- Full suite: `vinu-agent/tests` **840 passed**.

## Alignment with plan

- Steps 1-2 (locate the path, determine whether fallback existed): done — evidence above.
- Step 3 (port `_call_llm()`'s waterfall using providers the project already supports): done — the
  existing `openai`/`deepseek`/`anthropic`/`ollama` provider set is reused via the same
  `create_llm_from_config` builder.
- Step 4 (fallback on genuine failure, not latency): done — keyed on exceptions after the provider's
  own retries.
- Step 5 (log which provider served each call): done — `provider` tag + `LoggingChatLLM` records it.
- Acceptance criteria: clear yes (gap existed) with evidence; fallback added with a test that simulates
  the primary failing and the call succeeding via the fallback.

## Notes / out of scope

- `vinu-research/vinu_research/llm.py`'s `ResearchLlmClient` (the backtest loop's risk-critic) uses the
  infra `vinu-infra/llm/client_async.py::AsyncLlmClient`, which has its own explicit retry/backoff and
  Docker `alternative_urls`, but no cross-provider waterfall. It is a different service's path, not an
  agent team's; adding a waterfall there would follow the same pattern (via `vinu-infra`'s `LlmConfig`)
  if desired later. No agent-team call site needs anything beyond the above.
- Fallback config still requires the user to know which providers they have keys for (same information
  gap as task 03/08) — the mechanism is in place and tested; which providers are live is deployment
  config.