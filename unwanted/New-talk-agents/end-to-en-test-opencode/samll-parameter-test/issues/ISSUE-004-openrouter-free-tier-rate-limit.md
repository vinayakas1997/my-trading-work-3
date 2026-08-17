# ISSUE-004 — OpenRouter free-tier rate limiting floods LLM-heavy steps

- **Component:** vinu-news (LLM analysis), vinu-research (`vinu_lib/llm/client_async.py`), vinu-agent (OpenAI-style client) — all pointed at OpenRouter `google/gemma-4-31b-it:free`
- **Phase found:** 3
- **Severity:** HIGH (for LLM-dependent test paths)

## Description
The free model is aggressively rate-limited. In the AAPL pipeline's vinu-news step the client logged 19,503 LLM calls in the run window: 19,416 HTTP 429 + 1×503, 86 success (99.6% failure). The step's HTTP client gave up after a 30s read timeout (pipeline report: 206 calls / 192 failed from its own counter) — the request hung server-side under the retry/backoff flood. Research's in-run gemma calls all hit 429 (retried 3× then fail-closed). Agent hit the daily free-tier quota mid-session (`free-models-per-day-high-balance`, `X-RateLimit-Remaining: 0`, reset timestamp in response).

## Steps to reproduce
1. `.env` with `VINU_LLM_BASE_URL=https://openrouter.ai/api/v1`, model `google/gemma-4-31b-it:free`.
2. `python run_pipeline.py --ticker AAPL ... --verbose` (news step).
3. `POST /research/run`, or create an agent session and send a message.

## Actual
- vinu-news: step error `Read timed out (read timeout=30)`; server continues producing ~19.5k LLM attempts.
- research: completes but with 0 successful LLM calls in window (degraded fallback path).
- agent: assistant reply = the 429 error text as a message.

## Expected
LLM calls succeed within retry budget and steps complete with real LLM output.

## Impact
News/research/agent LLM paths cannot be fully exercised on the free tier; results are degraded. This is an environment/rate-limit reality, not a code bug — the fail-closed behavior is correct.

## Suggested fix
- For testing: pay for a non-free model, or reduce news `--news-articles` and raise timeouts/retries.
- For production: use a real provider key; add per-step retry budget awareness.
- The 429 handling (retry 3× with backoff, fail closed) is correct; the free tier just has too low a ceiling.

## Status
OPEN (environment constraint)

## Evidence
- `evidence/06-research/pipeline-aapl-news-fail.json` (news step error)
- Container `/data/llm_calls.jsonl` (news-api: 19,503 calls in window, 19,417 failed)
- `docker compose logs research-api` (429 retry/backoff logs)
- Agent session 686b070db934 assistant message (429 quota error)
