# S-10: Native Function-Calling Instead of Text-Prompted JSON

## What It Is

`00-vision.md`'s Layer 6 ("Seeking Information") already proposes adding tool use
so the LLM can query for more data when stuck — that's about giving the LLM new
*capabilities*. This suggestion is narrower and orthogonal: it's about *how* you
get structured output back from the LLM at all, for the calls you already make.

Today, every structured LLM response (`diagnose_failure`, `characterize_stock`,
`suggest_pivot`, `validate_idea`, strategy generation) works by instructing the
model in plain text — "Return JSON with this exact schema: {...}" — then parsing
whatever text comes back via `chat_json()`, with callers defensively doing
`response.get(key, "")` for every field. Both Vibe-Trading and fincept-terminal's
`deepagents` wrapper instead delegate schema conformance to the *provider*: tool
arguments arrive already parsed as a dict via native function-calling
(`Vibe-Trading/agent/src/providers/chat.py`, `ToolCallRequest.arguments`), or via a
Pydantic `response_format` wrapped in a `ToolStrategy`
(`ref-fincept-terminal/.../deepagents/agent.py:260-290`) — the model literally
cannot return malformed JSON because the API enforces the schema.

## Why It's Required

Text-prompted JSON is the least reliable way to get structured output from an LLM
— it's why every call site in `llm.py`/`loop.py` has defensive
`if response and isinstance(response, dict)` and `.get(key, "")` fallback code.
That defensive code isn't a design choice, it's a symptom: something you're
protecting against precisely because the format contract with the model is a
suggestion, not a guarantee. Neither FinRobot nor fincept-terminal's core router
actually solves this well either (fincept's router silently falls back to keyword
matching on a parse failure rather than re-prompting) — so this isn't "everyone
else has this solved and you don't," it's a genuine, still-open opportunity.

## Impact

- **If unfixed:** every new structured LLM call added (and P1-P4 added five of
  them) needs its own defensive parsing boilerplate, and a malformed response
  degrades silently to empty-string defaults rather than failing loudly or
  retrying.
- **If fixed:** malformed structured output becomes structurally impossible (for
  providers that support it) rather than something to defend against per call
  site — removes a whole class of defensive code and silent-degrade bugs.

## How to Use Effectively

1. Check whether your current LLM provider/client library
   (`ResearchLlmClient`/whatever underlies `chat_json`) already supports
   function-calling or a structured-output mode (most major providers do). If so,
   this is a refactor of `chat_json()` itself, not of every call site — define a
   JSON-schema per call type (you already have the shape, e.g.
   `DIAGNOSIS_SYSTEM_PROMPT`'s described schema) and pass it as a tool/function
   definition instead of embedding it in prompt text.
2. This is the highest-effort item in this suggestion set — it touches every LLM
   call site's plumbing, even if the call sites' logic doesn't change. Do it as a
   dedicated refactor, not bundled with a feature change, and validate one call
   site (e.g. `diagnose_failure`, lowest-stakes) before converting the rest.
3. Keep the `.get(key, "")` defensive fallbacks even after this change for
   fields the schema marks optional — schema enforcement guarantees *shape*, not
   that every optional field is populated with something useful.
4. This pairs well with **S-11** (confidence scoring) — if you're touching the
   schema for every structured call anyway, add a `confidence: float` field to
   each at the same time rather than as a separate migration.

## Implementation Hint — Where This Fits Today

**Entry point:** `ResearchLlmClient.chat_json(system, user)` (`llm.py`, near the
bottom of the class) — this single method is the funnel every one of the 7
structured-output call sites goes through (`chat_json` itself, plus
`diagnose_failure`, `characterize_stock`, `suggest_pivot`, `validate_idea`, and
`llm_generator.py`'s strategy generation calls). Whatever underlying provider
client `self._client` wraps (not shown in the files audited here — check what
`self._client.chat_json` actually calls into, likely an `httpx`/SDK call in a
provider-adapter module) is where function-calling support needs to be added.

**First thing a new agent should do before writing any code:** find
`self._client`'s class definition and check whether the underlying SDK/API client
already exposes a function-calling or structured-output parameter (most do) — if
it does, this is "pass a schema parameter instead of embedding schema text in the
prompt," a localized change to `chat_json()`'s implementation. If the provider
truly doesn't support it, this suggestion isn't actionable yet and should be
parked, not worked around with a manual JSON-repair loop (which is more
machinery than the schema-in-prompt-text status quo, for uncertain benefit).

**Rollout order:** convert one call site first — `diagnose_failure` is the best
candidate (simple schema: `root_cause`, `category`, `evidence`, `recommendation`,
all strings; low stakes since it's advisory text) — before touching the other
six, since this changes `chat_json()`'s contract and every caller needs to keep
working.

## Potential Bugs to Watch For While Testing

- **Optional fields may now be *required*-shaped even when logically optional.**
  Some providers' function-calling/structured-output modes require every schema
  field to be present (using `null` for "no value") rather than letting the
  model omit it the way free-text JSON allowed. Test that every existing
  `.get(key, "")` call site still gets something sensible — a schema-enforced
  `null` needs the same fallback handling as a missing key did before, don't
  assume the switch makes those defensive lines unnecessary.
- **Don't delete the defensive `.get()`/`isinstance()` checks.** Even with a
  provider-enforced schema, a provider bug, a downgraded model, or a
  misconfigured client can still return something unexpected. Test by
  deliberately feeding a malformed/empty response through the new code path (mock
  the client) and confirm it degrades the same way the old code did, rather than
  raising an unhandled exception because the defensive check was removed as
  "no longer needed."
- **This changes behavior for all 7 call sites at once if `chat_json()` itself is
  the conversion point.** Test each of the 7 call sites individually after the
  change, not just the one you were focused on converting first — a shared
  choke-point change has blast radius across every caller, and it's easy to
  verify only the call site you were thinking about.
- **SDK/dependency version bump risk.** If function-calling support requires
  upgrading the underlying provider SDK, test that the upgrade doesn't change
  behavior for *other*, unrelated `chat_json()` callers in the codebase that
  aren't part of this migration.
