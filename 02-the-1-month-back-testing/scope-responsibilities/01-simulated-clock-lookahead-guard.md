---
name: simulated-clock-lookahead-guard
component: vinu-agent
status: not-started
---

# Item 1 — Simulated Clock + Lookahead Guard

## What this is

A way to tell a `vinu-agent` session "believe it is `2026-07-06T09:30:00Z`,
not the real current time" — and, critically, prevent every data tool it
calls from returning anything dated after that point. Without the second
half, the first half is worthless: an LLM that thinks it's July 6th but
can still call `get_news` with an end_date of today has full lookahead and
any "profit" it produces during replay is fabricated, the exact mistake
`WeightSimulator`'s `shift(1)` (`vinu-simulator/engine/simulator.py:106`)
exists to prevent in the numeric backtester.

## Design constraint — this must be additive only

Every file touched here is also used by real live/paper trading sessions
(Stage 2). The default behavior (no `as_of` set) must be byte-for-byte
identical to what exists today. Every change below is "if this new field
is present, do X; otherwise, exactly today's behavior."

## Files to touch

### `vinu_agent/server/schemas.py`
- `CreateSessionRequest` (line 7-8): add `as_of: str | None = None` (ISO
  8601 UTC string, e.g. `"2026-07-06T09:30:00Z"`).

### `vinu_agent/server/routes_sessions.py`
- `create_session` (line 20-28): pass `req.as_of` through to
  `svc.create_session(title=req.title, as_of=req.as_of)`.

### `vinu_agent/service.py` / `vinu_agent/session/service.py`
- `create_session`: accept `as_of: str | None = None`, store it as
  `session.config["as_of"] = as_of` on the `Session` object
  (`vinu_agent/session/models.py:39` — the existing free-form `config`
  dict, no schema/migration needed).
- `_run_with_agent` (`session/service.py:124-183`): read
  `as_of = self.store.get_session(session_id).config.get("as_of")` and
  pass it to both `build_registry(...)` (line 131) and
  `ContextBuilder(...)` (line 141).

### `vinu_agent/agent/context.py`
- `ContextBuilder.__init__` (line 84-98, the second, active `__init__` —
  note the file currently has two `__init__` defs, the first is dead code
  shadowed by the second; don't touch that pre-existing oddity unless it
  actively conflicts with this change): add `as_of: str | None = None`
  parameter, store as `self.as_of`.
- `build_system_prompt` (line 51-73): change
  `current_datetime=_utc_now_iso()` to
  `current_datetime=self.as_of or _utc_now_iso()`.
- Also add one line to the system prompt template noting when a session
  is a replay (e.g. append `"\n**REPLAY MODE — this is historical data,
  not live.**"` when `self.as_of` is set) so the LLM's own behavior isn't
  silently different for a reason it can't see in its own context — if
  the agent's tone or caution changes materially when it knows vs. doesn't
  know it's a replay, that itself is worth recording in item 5's rubric.

### `vinu_agent/tools/__init__.py`
- `build_registry` (line 26-51): add `as_of: str | None = None` parameter.
  After `tool = cls()` (existing loop), add:
  ```python
  if hasattr(tool, "_as_of"):
      tool._as_of = as_of
  ```
  matching the exact existing pattern for `_session_id`/`_event_callback`.

### Each date-sensitive tool — add `_as_of: str | None = None` class attribute, clamp in `execute()`
- `vinu_agent/tools/news_tool.py` (`NewsTool`, line 5-29): if `self._as_of`
  is set, clamp `end_date` to `min(kwargs.get('end_date'), self._as_of)`
  (or reject a later end_date outright — pick one, document which, and
  make it loud in the tool's returned JSON, e.g. `"clamped_end_date":
  true`, not a silent truncation nobody notices).
- `vinu_agent/tools/stock_price_tool.py`: same clamp on whatever its
  date-range parameter is called — read the file first, the exact
  parameter name isn't confirmed here.
- Any `vinu-initial-analysis`-backed tool (angle/correlation/significance
  lookups) — same clamp.
- `vinu_agent/tools/options_tool.py` (`OptionsGreeksTool`): this tool is
  **live-snapshot only, no historical lookup at all** (see
  `the-stage-2-claude/scope-responsibilities/04-options-greeks-tool.md`).
  When `self._as_of` is set, `execute()` must return a clean
  `{"status": "unavailable", "reason": "options Greeks/IV have no
  historical lookup; not available in replay mode"}` — do not attempt to
  serve live data and pretend it's from the replay date.
- `vinu_agent/tools/trade_tool.py` — see item 2's scope doc; this file's
  broker instantiation is item 2's responsibility, not item 1's, but the
  `_as_of` attribute should still land here too since the tool needs to
  know the replay date to pass to the historical broker for fill pricing.

## Expected output / how to verify

- Create a normal session (`as_of` omitted) exactly as before — confirm
  `Current time:` in the system prompt is real UTC now, and every tool
  call behaves identically to pre-change (run the existing Stage 2 smoke
  test from `the-stage-2-claude/testing-status/stage2-readiness-verification/`
  again after this change to confirm no regression).
- Create a session with `as_of: "2026-07-06T09:30:00Z"` and ask the LLM
  to fetch news for AAPL with no end_date, then with an explicit end_date
  of today's real date — confirm both come back clamped to on-or-before
  2026-07-06, and confirm the tool's response makes the clamp visible
  (not a silent difference you'd have to diff yourself to notice).
- Confirm `get_options_greeks` returns the explicit "unavailable in
  replay mode" response, not live data, when `as_of` is set.
- Confirm the system prompt actually shows the replay-mode marker text
  when `as_of` is set.
