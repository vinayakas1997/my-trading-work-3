# S-03: Batch Evidence Writes and Add Write Locking

## What It Is

Two related inefficiencies in `hypothesis_registry.py` that none of R-A..R-E
touched:

**1. One full file rewrite per iteration.** `loop.py:449-467` calls
`add_evidence()` once per iteration in a loop over `history`. Each call does a
full `_load()` (read + `json.loads` the *entire* `hypotheses.json`, every
hypothesis for every symbol) and a full `_write()` (serialize everything, write a
temp file, `fsync`, `os.replace`). For a 5-iteration run that's 5 full read+write
cycles of a file that only grows over time — never trimmed (see below).

**2. No locking on the read-modify-write cycle.** The comment at
`hypothesis_registry.py:41-43` explicitly notes the previous `fcntl.flock` was
removed because it "only locked the private temp file anyway" — true, but that
means there is now *no* protection at all against two concurrent writers (two
research runs for different symbols, both landing on the same shared
`~/.vinu/hypotheses.json`) racing: process A loads the file, process B loads the
same snapshot, A writes, B writes — B's write silently discards A's update. This
is exactly the mechanism Vibe-Trading's atomic-replace-only writer *also* has (see
`registry.py:359-366` in the audit) — so this isn't unique to `vinu_research`, but
it's worth being deliberate about rather than accidental.

## Why It's Required

- The batching issue matters once run volume increases (scheduled jobs, S-12
  wiring, multiple symbols per day) — O(iterations) full-file I/O per run doesn't
  scale gracefully as `hypotheses.json` grows with every symbol you've ever
  researched.
- The locking issue matters the moment two research runs are ever in flight at the
  same time — which is already possible today: `service.py`'s `run_research()` is
  exposed over an async HTTP route (`server/routes_read.py:47`), so two concurrent
  requests for *different* symbols already share one JSON file with no protection.

## Impact

- **If unfixed:** as usage grows, expect occasional "hypothesis evidence I know I
  added isn't there" reports that are genuinely hard to reproduce (a race, not a
  logic bug) — the worst kind of bug to debug. Full-file I/O cost also scales
  linearly with total hypothesis count, not with the current run, so it gets
  slower for everyone as the file grows.
- **If fixed:** evidence writes become O(1) file operations per run instead of
  O(iterations), and concurrent runs stop being able to silently clobber each
  other's hypothesis updates.

## How to Use Effectively

1. **Batch first (cheap, no design risk):** change `loop.py`'s evidence loop to
   build the full list of `Evidence` objects in memory, then add a single
   `HypothesisRegistry.add_evidence_batch(hypothesis_id, evidence_list)` that does
   one `_load()` + one `_write()` for the whole batch. This alone removes most of
   the I/O cost without touching concurrency semantics.
2. **Locking (moderate effort):** wrap `_load()`+mutate+`_write()` in a real
   cross-process lock scoped to the *hypothesis file itself*, not just the temp
   file — on Windows use `msvcrt.locking()` or a sidecar `.lock` file with
   `portalocker`/`filelock` (already a common dependency in this ecosystem); on
   POSIX, `fcntl.flock` on the real path, not the temp path (which is what the
   removed code got wrong — lock the target file, not the private copy).
3. Do this before scaling up scheduled/concurrent runs (see S-12's kill-switch
   file for why "before you need it" matters for anything touching shared mutable
   state under concurrency).
4. Consider whether `HypothesisRegistry` should be a long-lived singleton with an
   in-process `asyncio.Lock` in addition to the cross-process file lock — that
   handles the common case (multiple runs in the same server process) cheaply
   without waiting on filesystem locking for every write.

## Implementation Hint — Where This Fits Today

**Entry points, two independent changes:**

- **Batching:** `loop.py:449-467` is the *only* call site of `add_evidence()`
  (confirm with a repo-wide grep before changing the registry API — if that's
  still the only caller, it's safe to change the call shape without touching
  other consumers). Add `HypothesisRegistry.add_evidence_batch(hypothesis_id,
  evidence_list: list[Evidence])` next to the existing `add_evidence()`
  (`hypothesis_registry.py:177-196`) — same body, just loop over the list once
  before the single `_write()` at the end instead of once per item.
- **Locking:** wrap the body of `_load()`+mutate+`_write()` in every mutating
  method (`create`, `update`, `delete`, `link_backtest`, `add_evidence`,
  `reject_with_reason`) — all six already funnel through the same `_load()`/
  `_write()` pair (`hypothesis_registry.py:23-57`), so a single lock acquired at
  the top of each public mutating method and released after `_write()` covers
  every path with one change, not six.

**Why this is feasible right now:** `_write()`'s atomic temp-file-then-`os.replace()`
(`hypothesis_registry.py:33-57`) is already correct as a write primitive — you are
not fixing the write, you're serializing access to the load-mutate-write sequence
around it. This means the change is additive (a lock acquisition/release wrapper),
not a rewrite of the storage format or the atomic-write logic.

**Platform note:** this project runs on Windows (per the dev environment used for
the audit) — `fcntl` isn't available. Use `msvcrt.locking()` directly, or reach for
a cross-platform library (`filelock`/`portalocker`) rather than hand-rolling
POSIX-only locking again, which is exactly the mistake the removed `fcntl.flock`
code made (per the comment at `hypothesis_registry.py:41-43`).

## Potential Bugs to Watch For While Testing

- **Batching changes the crash-failure mode.** Today, if the process dies
  mid-run, evidence already written via per-iteration calls survives up to the
  last completed iteration. If evidence is batched to write once at the end of
  `run()`, a crash mid-run now loses *all* evidence for that run, not just the
  unwritten tail. Test the "process dies after iteration 3 of 5" scenario
  explicitly — it fails differently after this change, not just faster.
- **Re-entrant lock deadlock.** If `add_evidence_batch()` is implemented as a
  loop calling the existing single-item `add_evidence()` under an *additional*
  outer lock, and `add_evidence()` also acquires the same non-reentrant lock
  internally, this deadlocks immediately. Test that the batch method either
  reimplements the body directly (no nested call) or that the lock used is
  explicitly reentrant.
- **Stale lock after a crash.** If a process holds the lock and is killed
  (not a clean exit), test whether the lock is a PID-aware library (`filelock`
  handles this) or a raw sentinel file that would wedge every future run
  indefinitely. This is the single most important case to test manually — kill
  `-9` (or Windows equivalent) a process mid-write and confirm the *next* run
  isn't permanently blocked.
- **In-process lock gives false confidence against cross-process concurrency.**
  If you add an `asyncio.Lock` but the real deployment runs multiple worker
  processes (check how the API server is actually deployed — `uvicorn` with
  multiple workers, gunicorn, etc.), the in-process lock does nothing for the
  actual race. Test with two genuinely separate OS processes writing
  concurrently, not two coroutines in one process — the latter can pass while
  the real bug remains.
- **Windows locking semantics differ from POSIX.** `msvcrt.locking()` locks a
  byte range, not the whole file, and behaves differently under retry/error
  conditions than `fcntl.flock`. Test the actual lock/unlock cycle on the
  platform this runs on, not just against documentation.
