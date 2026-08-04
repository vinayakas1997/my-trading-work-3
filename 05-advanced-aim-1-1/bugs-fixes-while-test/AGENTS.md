---
name: e2e-telemetry-bugs-fixes
status: reference
purpose: index of every bug/inconsistency found while running end-to-end-test.md against the real Docker stack, one file per issue, named after the issue itself. Same pattern as 04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/AGENTS.md — empty until the next agent actually runs the checklist.
---

# Bugs & Fixes Found While Verifying the Telemetry Layer End to End

Empty so far — `end-to-end-test.md` has not been run against the real
stack yet (built and unit-tested outside Docker, per `status.md`). This
file is the index once it has been; each finding gets its own file here,
named after the issue, not the fix — same convention
`04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/` already
established:

- What was wrong (with real evidence — a query result, a log line, a
  trace excerpt — not a description from memory).
- Why it mattered.
- What was changed to fix it (file:line).
- What was achieved / how it was verified.

## Index

None yet.

## Where to look first if something's wrong

- **Zero rows in `llm_calls`/`steps` at all**: check the telemetry DB path
  actually matches where the service is looking —
  `VINU_AGENT_DATA_ROOT`/`VINU_RESEARCH_DATA_ROOT` env vars, same class of
  bug as `04`'s
  [`data-root-docker-path-mismatch.md`](../../04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/data-root-docker-path-mismatch.md).
  `get_telemetry_store()` never guesses a default path — if the caller's
  `data_root` is wrong, telemetry writes to the wrong file silently
  (`record_llm_call_safe`/`record_step_safe` swallow all exceptions by
  design, per `AGENTS.md` — a wrong path won't crash anything, it'll just
  produce an empty table that looks like "nothing happened" instead of
  "wrote somewhere else").
- **`token_count_source` always `'estimated'` for `vinu-agent`, never
  `'provider'`**: the backing LLM server isn't returning a `usage` object
  — check directly against the raw HTTP response before assuming
  `agent/llm.py` has a bug (see `end-to-end-test.md` §2's checklist).
- **`retry_count` always `0` even on a call that's known to have failed
  and retried**: check `_is_transient_openai_error`/
  `_is_transient_anthropic_error` in `vinu-agent/vinu_agent/agent/llm.py`
  are correctly classifying whatever real exception type the actual SDK
  version installed raises — SDK exception hierarchies do change between
  versions, and this classification was written against `openai>=1.0`
  without pinning an exact version.
