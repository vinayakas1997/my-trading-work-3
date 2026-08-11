---
name: phase-0-test
status: proposed-not-built
purpose: concrete input/expected-output cases that prove Phase 0 works, in the same style as this project's real storage tests (direct construction + tempfile.TemporaryDirectory, no mocking -- matches tests/test_parquet.py's existing style).
---

# Phase 0 -- Test plan

Each case below is a real, nameable test (`test_<name>`), grouped by the
piece it covers, plus one end-to-end case that proves the three pieces
actually work together, not just in isolation. Written as
input -> expected output, so there's no ambiguity about what "done" means
for this phase.

## `TickerLedger`

**`test_add_event_writes_row`**
Input: construct `TickerLedgerStore` in a `tempfile.TemporaryDirectory()`,
call `add_event(ticker="AAPL", stage="summary_agent",
event_type="summary_refreshed", text="...", ref_id="run_abc123",
source="watchlist")`.
Expected: reading the row back returns all fields unchanged, and
`ledger_id` is a 12-character lowercase hex string (matches the project
convention: `uuid.uuid4().hex[:12]`, same as `team_runs.py`/`llm_calls.py`).

**`test_ref_id_and_source_default_to_empty_string`**
Input: `add_event(ticker="AAPL", stage="summary_agent",
event_type="summary_refreshed", text="...")` -- `ref_id`/`source` omitted.
Expected: no error; both columns store `""`, not `NULL`.

**`test_events_ordered_chronologically_per_ticker`**
Input: three `add_event` calls for `AAPL` at increasing timestamps,
interleaved with two calls for `MSFT`.
Expected: `get_events(ticker="AAPL")` returns exactly the 3 `AAPL` rows,
in ascending timestamp order, `MSFT` rows excluded entirely -- this is the
literal query pattern the design's rationale section is built on ("every
event for AAPL, in exact order").

**`test_no_update_or_delete_method_exists`**
Input: `hasattr(TickerLedgerStore, "update_event")`,
`hasattr(TickerLedgerStore, "delete_event")`.
Expected: both `False`. Append-only is enforced by the class not having
the method, not by a runtime check -- this test exists to catch a future
change that accidentally adds one back in.

## RunLog-driven trigger

**`test_no_new_run_id_skips_summary_agent`**
Input: `TickerSummaryStore.source_run_id` for `AAPL` already equals
`RunLog`'s current latest `run_id` for `AAPL`.
Expected: Summary Agent is not invoked (assert on call count, e.g. a
spy/counter, not a real LLM call in the test); `TickerSummaryStore` row
is unchanged.

**`test_new_run_id_triggers_summary_agent_once`**
Input: `RunLog`'s latest `run_id` for `AAPL` differs from
`TickerSummaryStore.source_run_id`.
Expected: Summary Agent invoked exactly once; afterward,
`TickerSummaryStore.source_run_id` equals the new `run_id`.

**`test_multiple_missed_run_ids_trigger_summary_agent_once`**
Input: `RunLog` has produced 3 new `run_id`s for `AAPL` since
`TickerSummaryStore.source_run_id` was last updated.
Expected: Summary Agent invoked exactly once, not 3 times -- the trigger
compares against "is there *a* newer id," it doesn't replay history.

**`test_runlog_unreachable_logs_distinct_failure_not_confused_with_no_change`**
Input: the `RunLog` check raises (simulated connection error).
Expected: Summary Agent not invoked (fail toward the cheaper outcome);
a `TickerLedger` (or equivalent log) entry distinct from a normal "no
change" outcome is recorded -- assert the two cases produce different,
distinguishable log entries, not the same one.

## Change-gate (`GATE`)

**`test_gate_no_change_returns_no_and_advances`**
Input: neither `TickerSummaryStore.source_run_id` nor this ticker's
artifact statuses (`SqliteStrategyStore.list_artifacts_for_symbol`) have
changed since the last recorded check for this ticker.
Expected: `GATE` returns `"no"`; Planner is not invoked; the watchlist
iterator's next call returns the *next* ticker, not this one again
(proves the "advance, not retry" edge, not just the return value).

**`test_gate_artifact_status_change_alone_returns_yes`**
Input: `source_run_id` unchanged, but an artifact for this ticker
transitioned status (e.g. BENCHING -> ACTIVE) since the last check.
Expected: `GATE` returns `"yes"`; Planner is invoked even though the
Summary Agent's underlying analysis didn't change -- proves the gate
checks *either* signal, not just the RunLog-driven one.

**`test_gate_lookup_error_defaults_to_yes`**
Input: `SqliteStrategyStore.list_artifacts_for_symbol` raises.
Expected: `GATE` returns `"yes"` -- the opposite failure direction from
the RunLog trigger's tests above, on purpose (see `02-guard-rail.md`):
here, skipping on an error risks hiding a real change, so the safe
default is to run the Planner, not skip it.

**`test_gate_state_updates_after_a_yes_pass`**
Input: `GATE` returns `"yes"`, Planner runs.
Expected: the per-ticker "last checked" state (`run_id` and/or artifact
status snapshot) updates such that an immediate second check on the same,
now-unchanged ticker returns `"no"` -- proves the gate doesn't re-fire on
the same change twice.

## End-to-end (proves the three pieces work together)

**`test_phase0_two_cycle_walkthrough`**
Input, cycle 1: `RunLog` has a fresh `run_id` for `AAPL` that
`TickerSummaryStore` hasn't seen yet.
Expected, cycle 1: RunLog trigger fires -> Summary Agent runs once ->
`TickerSummaryStore.source_run_id` updates -> `TickerLedger` gets exactly
one new row (`stage="summary_agent"`, `event_type="summary_refreshed"`) ->
`GATE` (checked immediately after, same cycle) returns `"yes"` since the
state changed within this pass.

Input, cycle 2 (immediately following, nothing changed in between):
Expected, cycle 2: RunLog trigger does not fire (no new `run_id`); `GATE`
returns `"no"`; zero LLM calls anywhere in this cycle for this ticker;
iteration advances to the next ticker in the watchlist.

This is the case that actually proves Phase 0 is "done" -- each piece
passing its own tests in isolation isn't sufficient, since the point of
this phase is that the three pieces hand off state to each other
correctly across cycles.
