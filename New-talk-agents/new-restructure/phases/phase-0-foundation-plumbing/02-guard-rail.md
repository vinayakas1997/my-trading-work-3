---
name: phase-0-guard-rail
status: proposed-not-built
purpose: what keeps Phase 0's plumbing robust and non-breaking once later phases start depending on it -- failure defaults, contention, and the things a first implementation would get wrong silently.
---

# Phase 0 -- Guard rails

## `TickerLedger`

**Append-only, enforced by API shape, not convention.** The store exposes
`add_event(...)` only -- no `update_event`/`delete_event` method exists at
all. An audit trail that *can* be edited isn't one; the guard here is
structural (the method doesn't exist), not a comment saying "don't."

**Write contention.** This store gets hit from more places than any
existing one in the project -- 8 real write points once every later phase
lands (Thesis Intake, Summary Agent, Planner, Researcher/Executor,
`risk_gatekeeper`, `capital_allocator`, Monitor, human override), several
of which can fire close together in the same cycle. Verify
`vinu_infra.sqlite.SQLiteBackend` already runs in WAL mode before Phase 1+
starts writing -- if it doesn't, this is the store where `SQLITE_BUSY`
under concurrent writes would actually surface, since no existing store
is written to from this many independent call sites.

**`ref_id` isn't a real foreign key.** `TickerLedger` and the store it
`ref_id`s into (e.g. `SqliteStrategyStore`) are separate SQLite files --
no cross-database FK constraint is possible, so a bug at any of the 8
write points could write an orphaned `ref_id` that no downstream reader
can resolve. Known, accepted limitation for Phase 0 -- not worth a
consistency-checking job yet since nothing writes here until later phases
land. Revisit if a real orphaned-`ref_id` case ever actually shows up in
practice, don't build the checker preemptively.

## RunLog-driven trigger

**Fail-closed direction, stated explicitly.** If the check against
`RunLog` errors (e.g. `vinu-initial-analysis` is unreachable), the correct
default is to **not** refresh the Summary Agent -- an LLM call against
possibly-unchanged data is wasted cost, not a safety issue, so there's no
reason to spend it on uncertain information. But this failure must be
logged as a distinct outcome from "genuinely no new `run_id`" -- if the two
cases look identical in the logs, a real `vinu-initial-analysis` outage
would silently look like "nothing's changing anywhere," which is a much
harder thing to notice and debug than a loud, distinct "staleness check
failed for N tickers this cycle."

**Compare against last-recorded id, never replay history.** If `RunLog`
produced three new `run_id`s for a ticker since the last check (e.g. the
Planner's cycle skipped a beat), the trigger fires once -- "is there
*a* newer `run_id` than what's recorded" -- not once per missed `run_id`.
A "catch up on every missed run" loop would burn 3 Summary Agent calls for
information one call already fully captures.

## Change-gate (`GATE`)

**Fail-closed direction here runs the opposite way from the RunLog
trigger, on purpose.** If the artifact-status lookup
(`SqliteStrategyStore.list_artifacts_for_symbol`) errors, the gate should
default to **"yes"** -- run the Planner anyway -- not "no." Skipping a
ticker because a lookup failed risks hiding a real change (an artifact
that actually did transition status) behind a transient DB error; that's
a correctness risk, not just a cost one, so it gets the opposite default
from the RunLog trigger above, where the failure mode is only ever "spent
one avoidable LLM call."

**The "no" edge must be an explicit advance, never a bare loop-back.**
This was already caught and fixed at the design level (`mermaid-
explanation.md`'s Loop-termination pass) -- `GATE`'s "no" edge reads
"advance to the NEXT ticker in the watchlist," not a retry of the current
one. The implementation must preserve this literally: a `continue` to the
next ticker in the iteration, never a re-check of the same ticker in the
same pass. Re-introducing a bare 2-node loop here at the code level after
the diagram was explicitly redrawn to rule it out would be a regression,
not a fresh bug.

**Read a consistent snapshot if the Planner's cycle is ever parallelized.**
Today this is presumably a single-threaded walk of the watchlist, so a
plain read-then-decide is fine. If ticker processing is ever parallelized
across workers, the artifact-status read this gate depends on needs to be
a consistent snapshot per ticker, not a value that could change between
the gate's check and the Planner actually running -- otherwise two workers
could both see "no" for the same real change and both skip it.
