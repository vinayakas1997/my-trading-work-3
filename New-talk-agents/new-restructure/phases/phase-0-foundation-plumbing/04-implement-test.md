---
name: phase-0-implement-test
status: built -- Phase 0 is implemented, tested, and wired
purpose: record of what was actually touched, what was tested, and the real result -- not a plan anymore, a report.
---

# Phase 0 -- Implementation record

Built 2026-08-11. Credentials also wired this session: OpenRouter
(`google/gemma-4-31b-it:free`, confirmed live/tool-calling-capable) and
Alpaca paper trading, both in `vinu-components/.env` (gitignored, real
values, not committed).

## Files touched

| File | Status | What changed |
|---|---|---|
| `vinu-components/.env` | new | Real OpenRouter + Alpaca-paper credentials, copied from `.env-example` and filled in. Gitignored -- confirmed via `git status`/`.gitignore` before writing. |
| `vinu-components/vinu-agent/vinu_agent/storage/ticker_ledger.py` | new | `TickerLedgerStore(SQLiteBackend)` -- schema exactly as specified in `01-plan.md`. `add_event()`, `get_events()`, `count_events()` (the last one added ahead of need, specifically for Phase 6/7's documented "query TickerLedger directly, don't maintain a separate counter" requirement). No `update_event`/`delete_event` -- append-only is structural. |
| `vinu-components/vinu-agent/tests/test_ticker_ledger_storage.py` | new | 6 tests, all passing. |
| `vinu-components/vinu-agent/vinu_agent/storage/ticker_summaries.py` | modified | `SCHEMA_VERSION` 1 -> 2, two new columns via `MIGRATIONS` (`ALTER TABLE ... ADD COLUMN`, same pattern as `team_runs.py`): `last_checked_run_id`, `last_checked_artifact_signature`. New method `record_gate_check()` -- deliberately separate from `upsert_summary()` so an artifact-status-only gate pass never falsely implies a new summary was written. |
| `vinu-components/vinu-agent/tests/test_ticker_summaries_storage.py` | modified | 3 new tests for `record_gate_check` added to the existing file; all 6 pre-existing tests still pass unmodified. |
| `vinu-components/vinu-initial-analysis/vinu_initial_analysis/server/routes_v1.py` | modified | New route `GET /v1/stage1/vinu-initial-analysis/latest-run/{ticker}` -- the single most recent run across ANY angle for a ticker. Not in the original 9-phase design docs verbatim, but required to make the RunLog trigger real: `RunLog.get_runs(symbol=..., limit=1)` already supported this exact query, only the HTTP route was missing. Flagged as an open item in `01-plan.md`'s "wherever the Planner's cycle currently begins iterating the watchlist" note -- resolved by building the missing piece rather than stubbing around it. |
| `vinu-components/vinu-initial-analysis/tests/test_api_v1.py` | modified | 3 new tests for `latest-run`; all 13 tests in the file (10 pre-existing + 3 new) pass. |
| `vinu-components/vinu-agent/vinu_agent/agent/ticker_gate.py` | new | `RunLogTrigger` (piece 2) + `HttpRunLogReader` (real transport, calls the new endpoint above) + `ChangeGate` (piece 3) + `run_gate_cycle()` (reference watchlist walk implementing the "no advances, never retries" edge literally). |
| `vinu-components/vinu-agent/tests/test_ticker_gate.py` | new | 9 tests covering every case in `03-test.md`'s RunLog-trigger, change-gate, and end-to-end sections, using fakes (`FakeRunLogReader`, `FakeStrategyStore`) -- no real HTTP or LLM call in any test, matching the test plan's own "spy/counter, not a real LLM call" instruction. |
| `vinu-components/vinu-agent/vinu_agent/service.py` | modified | `TickerLedgerStore` constructed in `AgentService.__init__` (`data_root / "ticker_ledger.db"`, same pattern as every other store), exposed via `.ticker_ledger` property, closed in `.close()`. `.ticker_summary_store` property also added (existed as a private attribute only before). Not threaded into `SessionService` yet -- Phase 0's own plan states no real write call site exists until later phases land, so nothing consumes it there yet. |

## Design deviation from `01-plan.md`, and why

The plan named the RunLog check abstractly ("has RunLog produced a run_id
newer than the one recorded") without settling the transport. Direct
Python import of `vinu_initial_analysis.storage.meta.RunLog` was
considered and rejected: `vinu-agent` and `vinu-initial-analysis` run in
separate Docker containers with separate `/data` mounts in the real
deployment (confirmed via `docker-compose.yml` earlier in this design
process) -- there is no real filesystem path from one container to the
other's SQLite file, so an in-process import would work in a same-process
test but silently break in the actual deployed system. Built the real
HTTP route instead (`HttpRunLogReader` calls it), with the fake-based
`RunLogReader` Protocol keeping every Phase 0 test itself fast and
network-free.

## Test results

```
vinu-agent:            479 passed (full suite, includes all Phase 0 tests)
vinu-initial-analysis: test_api_v1.py: 13 passed (includes 3 new latest-run tests)
                        full suite: 486 passed, 2 skipped, 0 failed (387.77s)
```

No regressions in either package's full suite from this phase's changes.

Every case from `03-test.md` has a corresponding real, passing test:
`TickerLedger`'s 4 cases, RunLog trigger's 4 cases, change-gate's 4 cases,
and the end-to-end two-cycle walkthrough -- all present in
`test_ticker_ledger_storage.py` / `test_ticker_gate.py`, all green.

## Known follow-ups (not blocking, not silently dropped)

- `ChangeGate`/`RunLogTrigger` are not yet called from any live scheduler
  loop -- none exists in the codebase today (confirmed earlier in this
  design process: no cron/APScheduler/while-loop anywhere outside
  CLI/channel files). `run_gate_cycle()` is ready to be the thing a real
  scheduler calls once Phase 1's sweep-engine wiring or a later phase
  introduces one; wiring it to something that actually runs periodically
  is follow-up work, not part of Phase 0's own scope.
- `google/gemma-4-31b-it:free` is a free-tier OpenRouter model -- can get
  rate-limited hard or rotate out without warning per OpenRouter's own
  docs. Nothing in Phase 0 calls the LLM yet, so this hasn't been
  exercised against a real failure; Phase 1+ (which does call it) should
  confirm the LLM client's own retry/fail-closed behavior before relying
  on it under load.
- `alpaca-details/details.md` (real paper-trading keys) is already
  tracked in git from a prior commit, predating this session. Paper-only,
  low risk, but flagged rather than silently left alone -- worth a
  deliberate decision (rotate the key, or `git rm --cached` it) outside
  the scope of this phase's own work.
