# S-13: `refresh_strategy()` Bypasses Every P1-P4 Feature

## What It Is

`service.py:307-341`'s `refresh_strategy()` calls `StrategyResearchLoop.run()`
directly, but constructs a fresh `StrategyResearchLoop` **without**
`hypothesis_registry` (compare `service.py:112` in `run_research()`, which passes
one, vs `service.py:323` in `refresh_strategy()`, which doesn't), and doesn't pass
`memory_context` or `run_id` either. This isn't a bug in the sense of crashing —
`loop.py`'s `self._hypothesis_registry is not None` guards mean it just silently
skips all hypothesis/memory features — but it means every refresh run gets none of
P1's memory injection, none of P3's hypothesis tracking, and (since no
`hypothesis_registry` means the evidence-writing block never executes) doesn't
even *record* what happened for future runs to learn from.

## Why It's Required

`refresh_strategy()` is specifically the code path invoked when decay is detected
on an already-*live* strategy (per `00-vision.md`'s "Live PnL attribution... →
triggers re-research" feedback loop) — arguably the highest-stakes research call
in the whole system, since it's deciding whether to keep trusting a strategy
that's currently trading. Right now that call gets *less* intelligence than a
routine exploratory `run_research()` call, not more.

## Impact

- **If unfixed:** refresh/decay-driven runs don't benefit from past-run memory
  (so a refresh could repeat a refinement that's already known not to work) and
  don't update the hypothesis registry (so a refresh's outcome — success or
  failure — is invisible to every future run on that symbol, including the next
  refresh attempt).
- **If fixed:** the highest-stakes research path (re-evaluating a live strategy)
  gets the same intelligence as exploratory research, and its outcome becomes
  part of the permanent record other runs can learn from.

## How to Use Effectively

1. Minimal fix: mirror `run_research()`'s setup in `refresh_strategy()` —
   instantiate `HypothesisRegistry()`, query/build `memory_context` the same way,
   pass both plus `run_id` (if `refresh_strategy` has access to a run record id —
   if not, that's a smaller prerequisite fix) into `loop.run()`.
2. Consider whether `refresh_strategy()` and `run_research()` should share a
   single internal helper for "set up a loop with all the intelligence wiring"
   rather than duplicating the setup — right now they've already diverged once
   (this gap), and every future addition to `run_research()`'s setup (S-01
   through S-11, wherever applicable) risks the same silent skip in
   `refresh_strategy()` unless the wiring is centralized.
3. This is a good one to fix early and cheaply — it's a small, mechanical change
   (wiring, not new logic) that immediately makes an existing high-stakes path
   consistent with the rest of the system.

## Implementation Hint — Where This Fits Today

**Entry point:** `service.py:321-333`, inside `refresh_strategy()` — directly
comparable, line for line, to `service.py:96-118`'s setup inside `run_research()`.
This is a diff-and-copy job: `run_research()` builds `memory_context` via
`get_past_run_summaries()` + `_build_memory_context()` (`service.py:100-106`),
constructs `HypothesisRegistry()` (`service.py:112`), and passes both plus
`run_id=record.id` into `loop.run()` (`service.py:118-128`). `refresh_strategy()`
does none of this — it just calls `StrategyResearchLoop(tools=tools,
config=self._config)` (`service.py:323-326`) with no registry, then
`loop.run(...)` (`service.py:327-333`) with no `memory_context`/`run_id` kwargs.

**Why this is feasible right now:** every piece needed already exists and is
already proven working in `run_research()` — this isn't new capability, it's
applying capability that already works in one place to a second place that was
missed. No design decisions needed, just parity.

**One real gap to resolve first:** `refresh_strategy()` doesn't currently have a
`ResearchRunRecord` (it operates on a `strategy_id` from `SqliteStrategyStore`,
not a fresh run in `ResearchStorage`) — so there's no `record.id` to pass as
`run_id` the way `run_research()` does. Decide whether refreshes should get their
own `ResearchRunRecord` (consistent with everything else being tracked in
`ResearchStorage`) before wiring this up, since that decision affects both this
suggestion and **S-02**'s evidence-linking for refresh-triggered evidence.

## Potential Bugs to Watch For While Testing

- **Refresh runs polluting memory context for *future* exploratory runs.** If
  `refresh_strategy()` starts inserting `ResearchRunRecord` rows so `run_id`
  wiring works, test that `get_past_run_summaries()` (used by memory injection,
  see S-04) doesn't then surface `"Refine existing strategy for X"` as if it were
  a distinct user-initiated idea in a future run's memory context — that's noise,
  not signal, for a fresh exploratory research request on the same symbol.
- **Empty-universe edge case.** `symbol=artifact.universe[0] if artifact.universe
  else ""` (`service.py:330`) — test what happens when `artifact.universe` is
  empty and this new wiring passes `symbol=""` into `HypothesisRegistry` lookups/
  `memory_context` queries. An empty string as a lookup key could match nothing
  (safe) or, worse, match some other malformed record that also has an empty
  symbol (a real risk once multiple bugs stack) — test the empty case explicitly
  rather than assuming it just falls through cleanly.
- **Reintroducing S-01's bug in a second place.** If hypothesis lookup is wired
  into `refresh_strategy()` before S-01's improved matching lands, this new code
  path inherits the *original* symbol-only collision bug fresh — test that
  whichever hypothesis-matching logic exists at the time (R-A's substring match
  or S-01's improved version) is actually reused here, not reimplemented
  separately and accidentally left on the old, more fragile behavior.
