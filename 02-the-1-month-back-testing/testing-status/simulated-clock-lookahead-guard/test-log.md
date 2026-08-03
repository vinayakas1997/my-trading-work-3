# simulated-clock-lookahead-guard — Test Log

## What will be tested / Expected output

- Create a normal session (`as_of` omitted) exactly as before — confirm
  `Current time:` in the system prompt is real UTC now, and every tool
  call behaves identically to pre-change (re-run the existing Stage 2
  smoke test from
  `the-stage-2-claude/testing-status/stage2-readiness-verification/`
  after this change to confirm no regression on the live path).
- Create a session with `as_of: "2026-07-06T09:30:00Z"` and ask the LLM
  to fetch news for AAPL with no end_date, then with an explicit end_date
  of today's real date — confirm both come back clamped to on-or-before
  2026-07-06, and confirm the tool's response makes the clamp visible
  (not a silent difference you'd have to diff yourself to notice).
- Confirm `get_options_greeks` returns an explicit "unavailable in replay
  mode" response, not live data, when `as_of` is set.
- Confirm the system prompt actually shows the replay-mode marker text
  when `as_of` is set.
- Full detail: [../../scope-responsibilities/01-simulated-clock-lookahead-guard.md](../../scope-responsibilities/01-simulated-clock-lookahead-guard.md)

## Design verification (2026-08-03) — read the actual code that item 1's
## seams claim to touch; confirms the plan is buildable as scoped, with two
## gaps that must be resolved at implementation time (both are additive-optional
## by design, so the live path stays untouched).

- `_run_with_agent` (`session/service.py:124`) is invoked **fresh per attempt**
  (each user message → new `run_in_executor` at line 90-95), and it rebuilds the
  tool registry (line 131) and a fresh `ContextBuilder` (line 141) every time.
  **Implication for mid-session advance:** as long as the harness updates the
  stored `session.config["as_of"]` *before* each day's message, the next
  `_run_with_agent` will re-read it and rebuild registry/context with the new
  value — no memoization to worry about. **But** the "read
  `config.get("as_of")`" line does not exist yet; it must be added to
  `_run_with_agent` (and the read must happen fresh each message, not cached).
- `Session.config` is a real persistent field (`session/models.py:39`,
  persisted via `to_dict`/`from_dict` lines 41-62) — storing `as_of` there
  needs **no schema migration**, exactly as the scope claims.
- `SessionStore.update_session()` exists (`session/store.py:22`) but is
  **not exposed via any HTTP route** — see Bug-1 below; this is the one real
  gap that will block the day-stepper harness.

### Bug-1 — mid-session config advance has no HTTP route (harness cannot
### advance `as_of` day to day)
- **Found during:** design verification for this item (the harness scope, item
  3, is HTTP-only by design). Verifying how a session's `as_of` would be
  mutated between daily messages.
- **Date:** 2026-08-03
- **Symptom:** `vinu_agent/server/routes_sessions.py` has create/list/get/
  delete/messages/cancel/events only — no `PATCH /sessions/{id}` or
  config-update endpoint. `CreateSessionRequest` (schemas.py:7-14) carries
  only `title` (no `config`/`as_of` either). So a harness creating one session
  and wanting to change `config['as_of']` each day has **no HTTP way to do it**.
  `update_session()` exists in `SessionStore` but nothing calls it.
- **Reproduction:** grep routes — every route is a GET/POST for
  create/list/get/delete/message/cancel/events; none mutates config.
- **Severity:** blocker for item 3 (reuse-same-session-across-days as scoped
  is impossible without an update-config endpoint). Item 1's own clock is
  unaffected.
- **Options when implementing (pick one, document which):** (a) add a
  `PATCH /sessions/{id}` route accepting `{"config": {...}}` (small, additive,
  live sessions unaffected), or (b) change item 3's harness to pass `as_of`
  per-message in the `SendMessageRequest` body instead of via session config —
  but that changes the sharing-`_as_of`-across-tools read-point in
  `_run_with_agent`, so (a) is closer to the scope's stated design.

### Bug-2 — `AgentLoop._build_result` returns only `history[-10:]`, not the
### full "thinking" item 3 needs
- **Found during:** verifying item 3's output source ("the full ordered trace...
  exactly as `AgentLoop.run`'s `full_history` already assembles it").
- **Date:** 2026-08-03
- **Symptom:** `_build_result` (agent/loop.py:396-414) returns
  `"history": history[-10:]` — only the last 10 messages. The full in-loop
  `full_history` (which genuinely interleaves assistant content + tool_calls +
  tool results, confirmed at loop.py:62,154,159) is **not returned or
  persisted**. So an HTTP-only harness (item 3) gets only the final assistant
  content (via messages.jsonl / `MessageResponse.content`), not the full trace
  item 3 wants to store in `thinking.json`.
- **Severity:** blocker for item 3's "thinking.json = full ordered trace" as
  scoped. The trace *is* assembled in-memory (good — no LLM change needed), it
  just isn't exposed.
- **Resolution options (document at implement time):** (a) have session service
  persist the full attempt trace to the attempt dir when `_as_of` is set (and
  have the harness read it from storage, not the HTTP response), or (b) add a
  non-default `get_attempt_trace` read path. Item 1/2 work is unaffected.

_More entries as implementation proceeds._

### Bug-3 — news tool returned 0 articles during replay (inverted date range)
- **Found during:** verifying the v3 smoke test
  (`results/schema-and-url-fix-smoke-test-v3/`) — the agent called
  `get_news` for AAPL without a `start_date` and got
  `{"count": 0, ..., "clamped_end_to_as_of": true}`, concluding "No news
  available for AAPL" while 168 articles existed in that window.
- **Date:** 2026-08-03
- **Symptom:** `NewsTool` clamps `to` to `_as_of` (replay date) but sends no
  `from`; the service falls back to `ts_days_ago(7)` computed from real
  wall-clock now (2026-08-03 → 2026-07-27), which is *after* the clamped
  `to` (2026-07-06). Inverted range → empty.
- **Reproduction:** `get_news` with no `start_date`, `_as_of=2026-07-06T13:30:00Z`.
- **Severity:** major — news is a core research input; silent empties would
  corrupt item 5's behavioral assessment.
- **Fix applied:** `vinu_agent/tools/news_tool.py` — when `_as_of` is set and
  no `start_date` given, derive `from_epoch = to_epoch - 30*86400` anchored to
  the replay date instead of relying on the service's real-now fallback.
- **Verification:** `NewsTool` with `_as_of` returns `count: 20` real AAPL
  headlines; service-level `get_ticker_news` with the same range returns 20.
- **Status:** fixed. Full precision in
  [FIXES-2026-08-03.md](../../FIXES-2026-08-03.md).

### Bug-4 — get_features 422: agent payload mismatched API schema, and no data-read path
- **Found during:** verifying the v3 smoke test trace (step 7:
  `Client error '422 Unprocessable Entity' for url 'http://features-api:8082/features/requests'`).
- **Date:** 2026-08-03
- **Symptom:** `features_tool.py` POSTed `{symbol, indicators, from_ts, to_ts}`
  but `FeatureRequestIn` requires `{title, symbols, features/preset, ...}`.
  Even after a payload fix, the POST returns only request metadata — there was
  no HTTP route returning the computed rows, and the agent container doesn't
  mount the features volume.
- **Reproduction:** any `get_features` call during replay.
- **Severity:** blocker for item 1's "agent can compute technical indicators
  in replay" claim — the tool could not produce a single indicator.
- **Fix applied:** added `get_request_data()` to `vinu_tools/service.py`,
  `GET /features/requests/{request_id}/data` to `routes_requests.py`, and
  rewrote `features_tool.py` to POST the correct schema then read `/data`.
- **Verification:** endpoint returns real rows (count 20); v4 smoke test step
  10 returned real AAPL features with `rsi_14` populated, and the agent quoted
  "RSI at 56.7" from it.
- **Status:** fixed. Full precision in
  [FIXES-2026-08-03.md](../../FIXES-2026-08-03.md).
