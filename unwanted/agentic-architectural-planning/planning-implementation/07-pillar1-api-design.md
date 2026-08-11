---
name: pillar1-api-design
status: synced-to-real-system
purpose: concrete answer to pillar 1 (API design) from ../archi-think-1.md, synced against the real vinu-research store interfaces found afterward -- the specific method names below (create_version, mark_lab_approved, ...) are superseded by real methods that already exist; what's still worth adopting is the narrow-method pattern itself, now aimed at the real store.
---

> **Synced, not thrown out.** The methods drafted below
> (`create_version`, `mark_lab_approved`, ...) don't exist and shouldn't
> be built — `SqliteStrategyStore` and `HypothesisRegistry` already have
> real interfaces that do this job:
>
> - `SqliteStrategyStore`: `upsert_artifact`, `get_artifact`,
>   `list_artifacts`, `list_artifacts_for_symbol`,
>   `list_artifacts_by_statuses`, `list_stale_artifacts`,
>   `delete_artifact`, plus `append_bench_entry`/`get_bench_history`,
>   `append_calibration_entry`/`get_calibration_entries`,
>   `save_snapshot`/`get_latest_snapshot`/`get_snapshots` (bench/decay/
>   calibration tracking this file never even proposed).
> - `HypothesisRegistry`: `create`, `get`, `update`, `delete`, `list_all`,
>   `link_backtest`, `add_evidence`, `add_evidence_batch`,
>   `reject_with_reason`, `query_by_symbol`, `search`, `count`.
>
> **What's still worth adopting — Done.** This file's core idea — narrow,
> single-purpose methods per state transition instead of one generic
> update — is now built on top of `SqliteStrategyStore.upsert_artifact()`
> (which still allows any field to change via one generic call, unchanged,
> see pillar 6's sync note): `transition_status(artifact_id, to_status)`
> plus named wrappers `mark_benching`/`mark_active`/`mark_monitoring`/
> `mark_decayed`/`mark_disabled`, each validating the current status
> against a real transition table before writing, raising
> `InvalidStatusTransition` otherwise. 11 tests in
> `vinu-research/tests/test_strategy_store_transitions.py`.

# Pillar 1 — API design

Reference: [../archi-think-1.md](../archi-think-1.md) (the 9 pillars),
pillars 5, 6, 7, 8, 9 (this file collects what they each already implied
into one interface spec per store).

## Not an HTTP API — the existing pattern is a plain Python store class

Nothing in vinu-agent exposes `team_runs`/`llm_calls` over HTTP today —
they're queried directly as Python objects (`TeamRunStore`,
`LlmCallLogStore`, both `SQLiteBackend` subclasses). The new stores
follow the same shape. "API design" here means: the actual method
signatures tools call, not a REST surface — consistent with everything
already built, not a new pattern layered on top.

## `StrategySpecStore`

```python
def create_version(
    symbol: str, direction: str,
    entry_condition: str, exit_condition: str,
    stop_loss: str, position_size_rule: str,
    angles_used: list[str], angles_missing: list[str],
    prior_lessons_considered: list[str],
    created_by_run_id: str,
    parent_spec_id: str | None = None,
) -> str: ...  # returns new spec_id -- NOT a tool (pillar 8): called by
                # strategist's / strategy_lab's TeamManager.run() after
                # parsing the specialist's final-answer JSON, same as
                # team_runs is written today

def get(spec_id: str) -> StrategySpec: ...

def get_latest_in_chain(spec_id: str) -> StrategySpec: ...
    # walks parent_spec_id forward to the newest version in this lineage

def list_by_symbol(symbol: str, status: str | None = None, limit: int = 50) -> list[StrategySpec]: ...

def list_by_status(status: str, limit: int = 50) -> list[StrategySpec]: ...
    # e.g. capital_allocator: list_by_status("gate_approved")

# One narrow method per state-machine edge (pillar 6/8) -- no generic
# advance_status(new_status) that could be called with the wrong value.
# None of these are agent tools (pillar 8) -- each is called directly by
# the owning team's own TeamManager.run(), after it reaches its verdict:
def mark_lab_approved(spec_id: str, run_id: str) -> None: ...   # strategy_lab's manager
def mark_lab_rejected(spec_id: str, run_id: str) -> None: ...   # strategy_lab's manager
def mark_gate_approved(spec_id: str, run_id: str) -> None: ...  # risk_gatekeeper's manager
def mark_gate_rejected(spec_id: str, run_id: str) -> None: ...  # risk_gatekeeper's manager
def mark_funded(spec_id: str, run_id: str, amount: float) -> None: ...      # capital_allocator's manager
def mark_not_funded(spec_id: str, run_id: str, reason: str) -> None: ...    # capital_allocator's manager
# mark_live / mark_closed: NOT here -- Phase 6 / position-close are
# external to vinu-agent (pillar 8's boundary note), written via
# whatever service-to-service path that system uses, not this class's
# interface at all.
```

Every `mark_*` method internally checks the row's current `status`
against the one allowed prior state before writing (pillar 6's state
machine) — calling `mark_funded` on a spec that isn't `gate_approved`
raises, it doesn't silently succeed.

## `MemoryLedgerStore`

```python
def record_lesson(
    symbol: str, setup_type: str, status: str, spec_id: str,
    summary: str, lessons: str, outcome_metrics: dict,
    created_by_run_id: str,
) -> str: ...  # returns ledger_id -- NOT a tool (pillar 8): called by
                # post_trade_review's TeamManager.run() after parsing
                # trade_narrator's final-answer text

def search(symbol: str, status: str | None = None, query: str | None = None, limit: int = 20) -> list[LedgerEntry]: ...
    # backs the search_strategy_ledger tool -- strategist, strategy_lab.enhancer
```

`record_lesson` checks for an existing entry with the same `spec_id`
before inserting (pillar 2's idempotency rule — a retried
`post_trade_review` run for the same closed position shouldn't produce
two lessons).

## `ShadowLedgerStore`

```python
def record_tick(shadow_id: str, spec_id: str, position_id: str, ts: int, price: float, unrealized_pnl: float, state: dict) -> None: ...
    # pillar 8: no agent tool wraps this at all -- deterministic infra only

def get_latest(position_id: str) -> ShadowSnapshot: ...
    # backs get_position_comparison's shadow side -- trade_monitor

def get_history(position_id: str, from_ts: int | None = None, to_ts: int | None = None) -> list[ShadowSnapshot]: ...
    # backs get_shadow_ledger_history -- post_trade_review
    # caller applies pillar 9's gap check: a gap larger than the
    # expected tick cadence means "not tracked during this window,"
    # not silently interpolated

def prune_older_than(cutoff: int, keep_summary: bool = True) -> int: ...
    # pillar 6's deletion policy -- returns count pruned, writes its own
    # prune-record per pillar 6 §4
```

## `team_runs` / `team_tasks` — additions to the existing store

```python
# new columns: related_spec_id (pillar 7), last_heartbeat_at (pillar 9)
# new status value: "stale" (pillar 9)

def list_by_spec_id(spec_id: str) -> list[TeamRun]: ...
    # pillar 7's traceability query -- capital_allocator, post_trade_review,
    # the manager-verification check

def bump_heartbeat(run_id: str) -> None: ...
    # called as each specialist delegation completes within a run

def reap_stale_runs(threshold_seconds: int) -> list[str]: ...
    # pillar 9's reaper -- returns run_ids just transitioned to "stale"
```

## Confirming the "latest via a real log, never mtime" discipline

`get_latest_in_chain` and `list_by_status` both resolve "current" purely
through SQL (`status`, `created_at`, `parent_spec_id`) — there's no
filesystem involved anywhere in these stores, so the specific bug this
project's existing rule guards against (`AngleStorage`'s "latest resolved
via a SQL run log, never filesystem mtime") can't recur here by
construction, not just by discipline.

## What every method above already inherited from earlier pillars

Nothing in this file introduces a new rule — it's the collection point:
narrow single-purpose write methods (pillar 6, 8), read methods scoped to
who's allowed to call them at the tool-registration layer (pillar 8),
idempotency checks where a retried event could double-write (pillar 2,
detailed next), and heartbeat/staleness on every run-tracking read
(pillar 9). Pillar 1 turned out to be mostly a matter of naming what the
other pillars had already decided.
