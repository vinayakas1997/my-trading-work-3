# 03. LLM gateway, the stuck-slot bug, and the fresh start (2026-10-06)

## What went wrong (root cause chain)

1. Research for the 10 screener picks produced nothing for 40 minutes.
2. The local model (llama.cpp, **one slot**) was busy with one request that never finished. Everyone else queued behind it and timed out after 5 minutes each.
3. That request had **no output limit**: `OpenAIChatLLM.chat` in the agent sent no `max_tokens` (`n_predict = -1` on the server). One degenerate answer can run forever and hold the only slot.
4. Why no test caught it: tests checked that a call returned an answer, never what the request contained.

Fixes: the agent client now sends `VINU_LLM_MAX_TOKENS` (default 8000) with every request; three tests.

## The LLM gateway (new service `llm-gateway`, port 8099)

Every service's `VINU_LLM_BASE_URL` now points at the gateway; only the gateway talks to the model server (`VINU_LLM_UPSTREAM_URL`). It speaks the OpenAI protocol, so callers changed only their base URL and send `X-Vinu-Caller` / `X-Vinu-Purpose` headers (`vinu_infra.llm.identity`, `purpose_scope(...)`).

| Piece | Behaviour |
|---|---|
| `llm_queue` (hot) | queued / running / done-not-yet-collected rows only; small, so the worker's scan stays fast |
| `llm_history` (archive) | every finished call: who, why, ticker, tokens, wait and run time, error, archive reason; big JSON stripped after 7 days |
| Move | one transaction when the caller has the answer (`delivered`), or `undelivered` (nobody collected within 10 min), `expired` (past its deadline), `cancelled` (caller hung up), `failed` |
| Priority | caller names a purpose; `priorities.py` maps it to 1..5 (1 live decision, 2 risk/feedback, 3 research, 4 planner/summaries, 5 hindsight/background). Unknown purpose is rejected. |
| Order | lowest number first, then first in; a waiting row gains one level per 300 s so priority 5 never starves; an urgent call waits only for the call already running |
| Retries | timeouts, connection errors, 408/425/429/5xx retried with backoff up to 3 attempts; other 4xx fail at once with the upstream's message |
| Hang-up | a caller that disconnects cancels its row: queued rows are dropped, a running call is aborted, so an abandoned request can no longer hold the slot |
| Identical calls | an identical request already queued or running shares one run |
| Key | rows hold `api_key_ref` (the NAME of a secret file); the value is read at call time and never stored. A test proves it never reaches the database. |
| Views | `GET /llm/queue` (who waits, longest wait, counters), `GET /llm/history?caller=` |

Deliberate choices: no `stream=true` (nothing in the stack streams; rejected with a message); a request with no `max_tokens` is capped at the default and counted in `max_tokens_defaulted` with a warning, instead of refused, so a caller that forgets it cannot be silently unbounded and also cannot break the chain mid switch-over.

Tests: 22 in `vinu-llm-gateway/tests` (priority order, aging, atomic archive, sweep, trim, retry timing, hang-up frees the slot, key never stored, unknown purpose), plus identity-header tests in infra and agent. All in-image suites: 0 failures.

### What the first real traffic showed (84 calls, pre-reset history)
- All delivered, no waiting, no retries, no failures.
- Many agent calls carry **27K to 35K token prompts** (context is 40,192) and return about 40 tokens: large context re-sent for tool steps. Earlier the server also saw a **56,574-token request**, which exceeds the context and fails. Worth trimming; not changed yet.
- All agent traffic is still tagged purpose `planner` (priority 4), including any live team decision. **To do:** set `purpose_scope("live_decision")` around live team runs and the live-decision worker.

## Other bugs found and fixed
| Bug | Effect | Fix |
|---|---|---|
| A candidate strategy whose code crashed for every symbol (simulator 422) escaped the research loop as HTTP 500 | 3 of 10 tickers (AMD, ACN, LIN) lost their whole run; the writer never saw the reason | `StrategyCrashed`: recorded as a REFINE iteration carrying the crash text; loop continues; test |
| `stale_images.py` joined `git status` paths (repo-root relative) to the sub-folder | uncommitted edits were never seen, so `deploy` said "nothing is stale" over old images | use the repo top-level; test with a real temp repo |
| `VINU_MODELS_ENABLED` never set, models-api dormant | every model angle tried for every ticker each cycle; ~100 tracebacks per 6 min buried real errors | set false in `.env`/`.env-example`; guard test (fails if models-api is profile-gated and the flag is not false) |

## First research results on the fixed stack (before the gateway took over)
7 of 10 tickers ran to a verdict, all `no_strategy_found`; 3 crashed (fixed above). Reasons recorded by the system: META 0 trades; TXN an edge that costs eat (Sharpe 0.11 free, 0.07 after costs); MSFT/TMO survive costs but fail validation; CAT Sharpe -0.84 even free; PM no edge. The bar was not lowered.

## Fresh start (`scripts/fresh_start.sh`)
Kept: price candles, news, model weights, watchlist, screener rules and tickers. Cleared (moved, not deleted, to `data/_backup_<UTC stamp>/`): agent, features, initial-analysis, live, llm-gateway, portfolio, reflection, research, simulator, strategy, strategy-evaluation, screener audit/rankers/snapshots/churn. Alpaca paper account is outside our data and untouched.

## Open
- Purpose for live team runs (above); prompt-size trimming.
- Initial analysis walks the 50-ticker watchlist alphabetically (about 4 min per ticker), so the screener's top picks wait behind AAPL, ABBV, ... unless the planner triggers them.
- The screener's startup call to the agent for held symbols fails if the agent is not up yet (warns, continues without them); `depends_on` does not order it.
- Everything in doc 02's open list that was not addressed here.


## Later the same day: what the gateway's records exposed, and what my own changes broke

| # | Problem | Root cause | Fix |
|---|---|---|---|
| 1 | 45 research LLM calls rejected (HTTP 400, request 44K to 79K tokens vs a 40,192 window) | the agent loop estimated 4 characters per token (dense numeric JSON is ~1.6) and ignored tool definitions; one tool result had no window-relative cap, so two results of 65K and 40K characters went out together | estimate at 2 chars/token plus tool definitions; cap one result at a quarter of the window; tests (found only because the gateway recorded every failed request) |
| 2 | Agent lost its context-window lookup | the gateway had no `/v1/models`, the agent asks for `n_ctx` there and fell back to a tiny default | gateway passes `/v1/models` through; HTTP-level gateway tests |
| 3 | Planner cycle and parallel ticker bootstrap failed after my purpose tagging | one shared `contextvars.Context` cannot be entered by two threads at once | `bind_context` copies per call; test with four simultaneous threads |
| 4 | A research team run showed `running` for 30+ minutes while doing nothing | its process died in a container restart; nothing ever closed the row, so the planner believed research was in progress | `vinu-agent reconcile-runs` at container start, before any worker (3 stuck runs cleared on first start); tests |
| 5 | Agent container crash-looped: `exec /app/entrypoint.sh: no such file or directory` | my edit tool saved `entrypoint.sh` with CRLF endings; `#!/bin/bash` cannot be resolved | restored LF; guard test on the bytes of every entrypoint and script |
| 6 | The deploy said "nothing is stale" over that broken image | git normalises line endings, so it saw no change; my stale check trusted git | the check also compares the modification time of the files a build would copy; test |
| 7 | Granger angle logged an ERROR traceback each run on short samples | asked for 12 lags; statsmodels allows about (n-1)//3 | cap the lag to the sample; tests |

Lesson recorded in the tests, not just here: three of these (3, 5, 6) were caused by my own changes and caught by (a) the in-image suites and (b) watching the live stack after each deploy. Both stay part of every change: deploy, run the suites in the image, then read the logs and the gateway history of the running system.
