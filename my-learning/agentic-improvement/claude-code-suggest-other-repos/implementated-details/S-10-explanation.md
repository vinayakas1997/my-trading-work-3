# S-10: Native Function-Calling — Explanation & Status

## What It Requires

1. **`ProviderCapabilities.supports_function_calling: bool`** — a new field on the
   `@dataclass(frozen=True)` in `vinu-lib/llm/providers.py` (line 16), defaulting to `False`.
2. **A provider-client adapter change** — `ResearchLlmClient.chat_json()` (the single
   funnel for all 7+ structured-output calls) currently delegates to
   `self._client.chat_json(...)`, which is a text-in/text-out call. To support
   native function-calling, the underlying async client needs a new method
   (e.g. `chat_with_tools()`) that accepts a JSON-schema tool definition and
   returns parsed arguments.
3. **Call-site migration** — each caller of `chat_json()` would pass a schema
   definition instead of embedding the schema in the prompt text. `diagnose_failure`
   is the recommended first target (lowest stakes, all-string schema).

## Current Status: ⏸️ BLOCKED

This suggestion is **deferred — not actionable without a provider-level API change**
in `vinu-lib.llm`.

### Why It's Blocked

| Layer | What Exists | What's Missing |
|-------|-------------|----------------|
| `ProviderCapabilities` (providers.py:15-25) | `capture_reasoning`, `send_reasoning_content`, `temperature_override`, `normalize_assistant_content`, `default_headers`, `supports_streaming`, `max_tokens_default`, `requires_api_key` | No `supports_function_calling` field |
| `providers.json` / `provider_defaults.json` | Per-provider config loaded in `_load_providers()` | No function-calling capability flag per provider |
| Async client (`self._client` in LLM client) | Supports `chat_json(system, user)` — text prompt → text response, JSON-parsed on the caller side | No `chat_with_tools(system, user, tools)` method; the underlying client call doesn't accept tool-call payloads |
| All 7 structured-output call sites | Use `response.get(key, "")` defensive parsing | Would need to switch to tool-argument extraction |

### Key Observation

The underlying async client is already called **exclusively via `chat_json()`**,
which is a text-in/text-out wrapper. Even if `ProviderCapabilities` gained a
`supports_function_calling` flag, there is **no plumbing in the client layer**
to send a tool-call payload or receive a parsed tool-response dict. Adding it
means:

1. Extending (or creating a subclass of) the provider adapter to expose a
   `chat_with_tools(...)` method.
2. Wiring the capability flag from `ProviderCapabilities` → client construction
   → `chat_json()` branching logic.
3. Testing all 7 call sites individually (blast radius on a shared choke-point).

### Recommendation

Park this suggestion for a **future refactor pass** that targets the provider
adapter layer specifically. When that layer gains tool-call support, this
suggestion becomes a mechanical migration of each `chat_json()` call site to
pass a schema — straightforward, but not useful to attempt until the
underlying client supports it.
