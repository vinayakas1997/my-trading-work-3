# S-08: A Real Decay-Monitoring Loop, Not Just an On-Demand Stub

## What It Is

`03-reference-patterns.md` already lists "rolling strategy update" (from Qlib) as a
Phase 2 roadmap item, and P4 delivered half of it: `service.py:307-341`'s
`refresh_strategy()` tries incremental refinement before falling back to full
re-research — but only when something *else* calls it. There's no process that
decides *when* to call it.

Vibe-Trading's `strategy-dev-manager` skill documents exactly this missing half
(`agent/src/skills/strategy-dev-manager/SKILL.md:112-125`): a batch health-check job
(`sdm_decay_scan(universe=...)`) that drives an explicit state machine —
`active → monitoring` (any metric enters a "Warning" band) → `decayed` (3+
consecutive scans land in a "Decayed" band) → `disabled` (a "Critical" reading).
This is a scheduled/recurring process, not a one-shot function waiting to be
called.

## Why It's Required

Your `HypothesisStatus` enum already has a `monitoring` value (`models.py`), and
your artifact model has `ACTIVE`/`MONITORING`/`DECAYED`/`DISABLED` states
(`models.py`, `ArtifactStatus`) — the state machine is *modeled* but nothing
currently drives the transitions automatically. Today, decay detection presumably
depends on something external deciding to check and calling `refresh_strategy()`
— which means an actively-decaying live strategy could sit in `ACTIVE` status
indefinitely if nothing happens to trigger a check.

## Impact

- **If unfixed:** the `ArtifactStatus.DECAYED`/`DISABLED` states exist in the model
  but have no automatic path to being reached — decay is only caught if something
  external remembers to look.
- **If fixed:** every active strategy gets a periodic health check with a
  documented multi-scan confirmation (not a single bad day triggering disablement
  — the "3+ consecutive scans" requirement specifically guards against noise-
  triggered disablement), and `refresh_strategy()` becomes the automatic response
  to a real signal instead of a manually-invoked tool.

## How to Use Effectively

1. This fits naturally next to `ScheduledResearchExecutor`
   (`vinu_research/scheduled/executor.py`) — you already have a poll-loop pattern
   there (`_run_loop`, `tick()`, `dispatch()`). Add a similar periodic job that,
   for each `ACTIVE` artifact, checks recent live-PnL/Sharpe against thresholds and
   moves it to `MONITORING` on the first bad reading.
2. Require multiple consecutive bad scans before `DECAYED`/`DISABLED` — copy Vibe-
   Trading's "3+ consecutive" rule rather than a single-scan trigger, specifically
   to avoid one noisy day disabling a strategy that's actually fine.
3. Wire `MONITORING`/`DECAYED` transitions to call `refresh_strategy()`
   automatically — that closes the loop P4 left half-open. On `DECAYED` (not yet
   `DISABLED`), attempt incremental refresh first (already implemented); only fall
   back to full re-research or `DISABLED` if refresh doesn't recover 80% of
   original Sharpe (the threshold `refresh_strategy()` already checks).
4. Log every transition through **S-05**'s trace log if it exists by then — decay
   transitions are exactly the kind of event you want a permanent audit trail for,
   since they directly affect what's live.

## Implementation Hint — Where This Fits Today

**Entry point:** `vinu_research/scheduled/executor.py`'s `ScheduledResearchExecutor`
class (`executor.py:19-143`). This already has every structural piece a decay-scan
job needs: `tick()` (`executor.py:42-56`, finds due work), `dispatch()`
(`executor.py:58-112`, does the work + reschedules), and `_run_loop()`
(`executor.py:130-138`, the poll-and-dispatch cycle) — a decay-scan job is a new
`ScheduledResearchJob`-shaped entry (or a parallel executor following the exact
same three-method shape), not a new scheduling framework.

**Why this is feasible right now:**
- `ArtifactStatus` (`models.py`) already has `ACTIVE`, `MONITORING`, `DECAYED`,
  `DISABLED` as enum values — the state machine this suggestion needs is already
  modeled in the type system, just never driven by anything automatic.
- `service.py:307-341`'s `refresh_strategy(strategy_id, new_data_end)` already
  implements the "try incremental refinement, fall back to full re-research if it
  doesn't hold 80% of original Sharpe" response — a decay-scan job's job is only
  to decide *when* to call this, not to reimplement what happens after.
- `SqliteStrategyStore` (imported in `service.py` as `strategy_store`) already
  holds `artifact.initial_sharpe` and presumably per-artifact identifying info —
  check what live-PnL/current-Sharpe data is already tracked there before adding
  new columns; the health-check comparison this needs may already have its inputs
  available.

**What's missing and is the actual new work:** something that periodically (a) 
lists `ACTIVE` artifacts, (b) compares current performance against
`initial_sharpe`/thresholds, (c) tracks consecutive bad readings (not currently
tracked anywhere — this is the one genuinely new piece of state), and (d) calls
`refresh_strategy()` automatically on the 3rd consecutive bad reading. Wire this
into the `ScheduledResearchExecutor`'s existing dispatch loop rather than building
a fifth standalone poller in this codebase.

## Potential Bugs to Watch For While Testing

- **Consecutive-bad-scan counter must survive a process restart.** If it's kept
  in memory in the executor process, a server restart silently resets it —
  test explicitly by restarting the process mid-sequence (e.g. after 2 of the
  required 3 bad scans) and confirm the count either persists (stored in SQLite/
  the artifact store) or that resetting it is a deliberate, tested decision, not
  an accident of implementation.
- **Stale/incomplete data producing false "bad" readings.** A scan that fires
  before genuinely new performance data exists (e.g. pre-market, or immediately
  after a strategy went live with only hours of data) could register a false
  decay signal from noise, not real underperformance. Test the scan explicitly
  skips or defers when there isn't enough new data to evaluate meaningfully.
- **Recovery must reset the counter.** Test that a *successful* `refresh_strategy()`
  call (returns `refreshed: True, full_research: False`, meaning it held 80% of
  original Sharpe) actually clears the consecutive-bad-scan counter — otherwise a
  strategy that recovers can still slide toward `DISABLED` on the next couple of
  scans because the counter never got reset, which defeats the whole point of
  "3 consecutive" being a noise filter.
- **Double-triggering.** Test the case where a scheduled decay scan and a
  manually-invoked `refresh_strategy()` call land on the same artifact around the
  same time — confirm they don't both kick off overlapping re-research runs for
  the same strategy (wasted LLM calls at minimum; at worst, two runs racing to
  update the same artifact/hypothesis record, which ties back to S-03's locking
  gap).
