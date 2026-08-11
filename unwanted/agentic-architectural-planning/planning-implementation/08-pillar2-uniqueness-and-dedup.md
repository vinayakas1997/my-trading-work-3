---
name: pillar2-uniqueness-and-dedup
status: checked-against-real-system-and-patched
purpose: concrete answer to pillar 2 (uniqueness and dedup) from ../archi-think-1.md -- ID format is a small, settled decision; dedup turns out to need two different answers for two different reasons (cost avoidance vs. correctness), each grounded in a real, already-existing precedent rather than invented fresh.
---

> **Checked against the real system, and it didn't hold up.** This file
> was marked "still open — not checked against `Artifact.create()`'s real
> hash-based ID scheme" in the index. It's now checked. §0 below is the
> problem that check found (the identity claim was simply wrong, and the
> dedup story assumed a store that doesn't behave the way this file
> assumed) and the fix applied to the real code for each part. Sections 1
> below are otherwise unchanged from the original design reasoning — the
> two-different-answers framing (cost vs. correctness) still holds, it was
> just resting on the wrong facts about the underlying stores.

## §0. What the real system does differently, and what was fixed

**1. Identity isn't UUID4 — it's a deterministic, unsalted hash, and
`upsert_artifact` is `INSERT OR REPLACE`.**

`Artifact.create()` (`vinu_research/models.py`) never used UUID4. The real
implementation was `art_` + the first 12 hex chars of
`sha256(f"{type}:{name}:{now}")` — no randomness at all. Two calls with the
same `type`/`name` at the same microsecond-resolution timestamp produced
the *identical* `artifact_id`, and `SqliteStrategyStore.upsert_artifact()`
is `INSERT OR REPLACE` on that ID — a collision (or a retried call)
wouldn't error, it would silently overwrite the earlier row.

That mattered concretely at the one real call site pillar 2's own
"correctness" argument is aimed at:
`vinu_agent/agent/research_artifact_writer.py::write_artifact_from_research_pass`.
It had no existence check at all — every time a `research` team's PASS
verdict was parsed it called `Artifact.create()` + `upsert_artifact()`
unconditionally. If that hook ever fired twice for the same run (a retried
delegation, the hook re-invoked after a downstream failure), you got two
separate BENCHING artifacts for one real research result — the exact
"retried event double-writes" failure mode this file says is already
solved by precedent, on a path where no such precedent was actually
applied.

**Fix:**
- `Artifact.create()` now folds `uuid.uuid4().hex` into the hash input, so
  the ID is genuinely non-deterministic — two calls can no longer collide
  just by landing in the same timestamp.
- `write_artifact_from_research_pass()` now looks up
  `strategy_store.list_artifacts_for_symbol(symbol)` and reuses an
  existing artifact whose `name` already matches the deterministic
  `{symbol}-research-{source_run_id}` key, instead of blindly creating a
  new one every call — the actual idempotency check pillar 2 assumed
  already existed here.

**2. The real dedup precedent for "correctness" (§2 below) doesn't use
`position_id` — because nothing in this codebase's broker layer has one.**

`memory_ledger`'s real backing store is `HypothesisRegistry`
(`vinu_research/hypothesis_registry.py`) — a single JSON file, rewritten
whole on every call (`_load()` the whole file → mutate in memory →
`_write()` the whole file back). It had **no lock of any kind** — the
in-code comment explicitly said "no file lock needed," reasoning only
about write *atomicity* (torn writes), never about two callers racing each
other. Two concurrent writers — plausible for real, since
`vinu_agent/service.py`'s `send_message`/`create_session` are `async def`,
meaning concurrent sessions are an intended usage pattern — would both
load the same base state, both mutate their own in-memory copy, and
whichever wrote second would silently overwrite the first's change. That's
strictly worse than the "duplicate row" failure this file worries about:
a duplicate is visible; a lost `add_evidence()` write is not, and it's
exactly the kind of "the org learns over time" data pillar 6 says must
never be corrupted.

Separately, the real position-close detector this file's §2 is modeled on
(`broker/debrief.py::PositionCloseDetector`) doesn't use `position_id` at
all — it can't, because `Position` (`broker/alpaca.py`,
`broker/historical_broker.py`) has no such field; it's a before/after diff
keyed on `symbol` against a local JSON snapshot file. That part isn't a
bug to fix — a broker position is naturally one-per-symbol, so symbol
*is* the closest thing to an identity this layer has, and the module's own
docstring already documents why the mechanism is poll-based (no
fill-event webhook exists here). But the *ordering* around it had a real
crash-duplication window: `_save_state()` was called once, after the loop
that writes evidence for every closed symbol. If the process died
mid-loop — after evidence was written for symbol A, before the loop
reached symbol B — the snapshot was never updated, so the next poll saw
A as still-open-then-closed again and re-wrote its evidence a second
time, with no idempotency check on the write side to catch it (see the
first point above).

**Fix:**
- `HypothesisRegistry` now has a real cross-process lock (`_locked()`, an
  exclusive-create lockfile with stale-lock detection, not the
  `fcntl.flock` the file itself notes was removed because it "was
  Unix-only and locked only the private temp file anyway") wrapping every
  load-mutate-write method (`create`, `update`, `delete`, `link_backtest`,
  `add_evidence`, `add_evidence_batch`, `reject_with_reason`). Concurrent
  callers now serialize instead of racing.
- `PositionCloseDetector.check_and_debrief()` now calls `_save_state()`
  *before* the evidence-writing loop, not after. A crash mid-loop can now
  drop at most one debrief (a swallowed miss — consistent with this
  class's own documented best-effort, failures-are-logged-and-swallowed
  contract) instead of silently duplicating one.

All existing tests for the touched files
(`test_hypothesis_registry.py`, `test_routes_hypothesis.py`,
`test_debrief.py`, `test_order_guard.py`, `test_research_artifact_writer.py`)
still pass unchanged after these fixes — none of the public method
signatures or return shapes changed, only what happens inside them under
retry/collision/concurrency.

## §0b. Follow-up: `debrief.py`'s "no `position_id`" gap, actually closed

§0's second point above deliberately did *not* try to fix the fact that
`PositionCloseDetector` only ever had `symbol` to key off, not a real
`position_id` — that was flagged as a structural broker-API limitation
(Alpaca nets to one position per symbol; there's no position-level ID to
begin with) rather than a bug, and the `_save_state`-before-loop ordering
fix above was scoped only to the crash-duplication window on top of that
existing symbol-diff mechanism.

Revisiting it: Alpaca (and `HistoricalFillBroker`, its drop-in replay
double) already expose real, unique **order-level** IDs via
`get_orders()` — that data was already being fetched for order-management
tools, just never used for close detection. That data source is what
`debrief.py`'s own docstring called "the fill-event webhook this codebase
doesn't have" — it doesn't need a webhook; a poll of closed-order history
already carries the same identity.

**Fix — a second, primary detection tier, with the original snapshot diff
kept as a fallback, not replaced:**

- `Order` (`vinu_agent/broker/alpaca.py`) gained a `filled_avg_price`
  field, parsed from Alpaca's real API response — the order-level fields
  that existed before never carried the actual fill price, only limit/stop
  prices. `HistoricalFillBroker.get_orders()` now populates the same field
  from its own replay fill data, so both brokers speak the same shape.
- `PositionCloseDetector.check_and_debrief()` now fetches
  `broker.get_orders(status="closed", limit=DEBRIEF_ORDER_LOOKBACK)` every
  poll and **replays** the filled buy/sell orders (oldest first) on top of
  the last known per-symbol `(qty, avg_entry_price)`. Every point a
  symbol's replayed quantity crosses from held to flat is a close, keyed
  by that specific sell order's own `order_id` — the real dedup identity
  pillar 2's original "correctness" argument wanted but the real
  `position_id`-free broker layer never had. This is also what makes a
  position that both opens *and* fully closes inside one polling gap
  visible at all — there's no `get_positions()` snapshot of the
  intermediate held state to diff against, but the fills that produced it
  are still in the order history.
- The original snapshot-diff mechanism (§0's second point) is kept as a
  **fallback tier**, not removed: anything the fetched order window missed
  (lookback too small, a position predating this detector's state file,
  the order API briefly unavailable) still gets caught the old way, with
  the same crash-safe "save state before writing evidence" ordering
  already applied.
- Config: `VINU_DEBRIEF_ORDER_LOOKBACK` (default `50`) controls how many
  recent closed orders are pulled per poll — added next to the existing
  `ALPACA_API_KEY`/`ALPACA_PAPER` env vars in `broker/alpaca.py`, same
  configuration pattern, so Alpaca stays the one configured broker source
  both live trading and this detection read from.

Net effect: `debrief.py` no longer needs a real `position_id` to get
`position_id`-grade identity — Alpaca's own order IDs, which were already
available and already unique per fill, do that job. The genuinely
unsolved piece from before (a broker-inherent one-position-per-symbol
limit, not a vinu-agent gap) is now fully absorbed by fill-level replay
instead.

Four new tests cover this
(`test_open_and_close_within_one_poll_is_still_detected`,
`test_fill_replay_dedups_on_order_id_not_reprocessed_next_poll`,
`test_broker_positions_win_over_replay_for_still_held_symbol`,
`test_get_orders_failure_falls_back_to_snapshot_diff_only`) alongside the
existing suite, all passing — `vinu-agent`'s full suite: 424 passed (was
420 before this change).

# Pillar 2 — uniqueness and dedup

Reference: [../archi-think-1.md](../archi-think-1.md) (the 9 pillars),
[../../../01-orchestrator-and-teams-architecture.md](../../../01-orchestrator-and-teams-architecture.md)
(where the `request_hash` dedup question was first flagged and left open).

## Identity — the small part

Every object gets a UUID4, assigned by the store at creation time — same
pattern `team_runs`/`team_tasks` already use, nothing new to decide here:
`spec_id`, `ledger_id`, `shadow_id` all follow it.

## Dedup — the part worth actually deciding, not leaving open again

The original architecture doc flagged this and left it unresolved
("if the same research question comes in twice, reuse a recent PASS
instead of re-running the whole team? Not yet decided"). Working through
the 8 teams surfaces that dedup isn't one question — it's two, for two
different reasons, and they need different answers.

### 1. Cost avoidance — `strategist` asked twice for the same thing

If `strategist` gets asked about the same symbol twice in a short window
with nothing new to go on (no new angle data, no new memory-ledger
entry), re-running the full specialist call is pure waste — real cost,
given the measured 14–276 second per-call latencies from the live
screener test.

**Answer:** compute a `request_hash` over the real inputs that would
change the output — `symbol` + the current angle-data snapshot's own
identity (e.g. its `run_id` from `AngleStorage`) + the current set of
`memory_ledger` entries for that symbol. If a `strategy_specs` row with
the same hash was created within a short reuse window (e.g. the last
hour) and hasn't been rejected, return it instead of delegating again.
This directly reuses `vinu-tools`' own existing `request_hash` pattern
rather than inventing a parallel scheme — the thing the original
architecture doc pointed at but never wired up.

### 2. Correctness — a retried event shouldn't double-write

Different problem: `post_trade_review` is triggered by a real external
event (a position closing). If that event gets delivered twice — a
retried webhook, a scheduler firing twice on the same close — running the
full review again isn't just wasteful, it's wrong: it would produce two
`memory_ledger` lessons for one real trade, corrupting the exact
"what's been tried before" history `strategist` is required to consult
(pillar 5).

**Answer:** don't invent a new mechanism — reuse the one that already
exists in this project for exactly this problem. `pnl_attribution`'s own
design doc states it plainly: "deduped by `position_id` so a retried
feedback-loop delivery never double-counts a closed trade." `record_lesson`
(pillar 1) applies the identical rule: check for an existing
`memory_ledger` row with the same `spec_id` before inserting. Real
precedent, not a fresh design.

## Why these needed to be two separate answers, not one

The cost-avoidance case is a soft optimization — reusing a recent result
is a *choice* made to save time, and a slightly-stale reuse is an
acceptable tradeoff within the window. The correctness case is a hard
constraint — writing the same lesson twice isn't just inefficient, it
actively corrupts data other teams depend on being accurate. Collapsing
both into one "dedup mechanism" would have either made the cost-avoidance
case too rigid (never allowing a legitimate second attempt) or the
correctness case too loose (a hash miss letting a real duplicate through).
Keeping them separate, with different triggers (a request pattern vs. an
external event identity) and different consequences of getting it wrong,
is the actual design decision here — not just where to put a hash check.

## What's still genuinely open

The exact reuse window for `strategist`'s dedup (an hour? tied to how
often the underlying angle data actually refreshes?) isn't decided — a
tuning parameter, not an architectural question, safe to leave for
whoever builds it to set based on real observed angle-refresh cadence.
