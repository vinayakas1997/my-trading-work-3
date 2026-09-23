# Plan: one shared gatekeeper in front of the ticker book

See `problem-explanation.md` for the confirmed gaps this closes. The
end goal, stated plainly by direction: stop letting each consumer of
ticker knowledge build its own separate read/parse logic in its own
separate place. One shared access layer, everyone reuses it, fixes
(freshness info, cluster titles, fail-open behavior) land once and
apply everywhere instead of drifting between copies.

## The pre-analysis book's real chapter structure (settled 2026-09-23)

Two big chapters, each with sub-chapters. Strictly bounded to the real
historical range this book covers (2022-01-01 -> the pre-analysis end
date) -- nothing live/ongoing beyond that boundary belongs in this book
(e.g. the 7-day trailing paper-trade rehearsal in `vinu_research/loop.py`
is live/ongoing past the cutoff, so it does NOT belong here).

**Chapter 1 -- Angles**
- 1a. Glossary (what each angle measures -- `explain_angle`, Step 1-2)
- 1b. Initial analysis, all tickers (per-ticker angle data, every real
  declared timeframe -- Step 13's `time_format="ALL"`)
- 1c. 7-cluster synthesis (`cluster_digest`)
- 1d. Cross-cluster analysis (`cross_cluster`)

**Chapter 2 -- Experience** (owned by `recording-the-experiece/`'s own
plan, not built here -- referenced so the gatekeeper's index stays
accurate once it exists)
- 2a. Simulation recorded results (intermediate backtest/simulation
  state, not just final outcomes, scoped to the same real time range)
- 2b. Shadow evaluator (`vinu-live/vinu_live/shadow_evaluator.py`'s
  ongoing post-ACTIVE strategy checks)

This gatekeeper's `chapter` parameter (design below) is shaped around
these two real chapters and their sub-chapters -- `"angles"` (with an
optional `sub` for 1a-1d) is buildable now; `"experience"` is a real,
named slot in the index but returns "not yet available" until
`recording-the-experiece/`'s plan actually ships it.

## Real evidence this is already starting to happen

`vinu-agent/vinu_agent/tools/trade_plan_tool.py::_read_summary_context`
is today's ONLY consumer of the book, and it has its own private
read/parse logic baked directly into that file (`store.get_summary`,
manual `getattr` fallbacks, its own field list). If a second consumer
needed the same ticker knowledge tomorrow, nothing stops it from
writing a second, slightly different version of the same logic. This
plan generalizes that one consumer's logic into a shared tool before a
second copy has a chance to exist.

## Design

### 1. A real book index -- the fix for "Cluster A means nothing on its own"

New module `vinu-agent/vinu_agent/tools/book_index.py`:

```python
from .angle_clusters import ANGLE_CLUSTERS

CLUSTER_INDEX: dict[str, dict[str, str | list[str]]] = {
    "A": {"title": "Classical statistical forecasts",
          "use": "cheap, transparent baseline forecasts -- sanity-check the heavier models against these",
          "members": ANGLE_CLUSTERS["A"]},
    "B": {"title": "Deep-learning / foundation-model forecasts",
          "use": "the ensemble -- consensus across 14 models catches signal one model alone would miss or fake",
          "members": ANGLE_CLUSTERS["B"]},
    "C": {"title": "Volatility & drawdown risk",
          "use": "how rough the ride could get, independent of direction",
          "members": ANGLE_CLUSTERS["C"]},
    "D": {"title": "Regime & trend structure",
          "use": "what kind of market this is, so the forecasts above get read in the right context",
          "members": ANGLE_CLUSTERS["D"]},
    "E": {"title": "Shock / personality behavior",
          "use": "flags a ticker reacting abnormally, so a 'normal-behavior' forecast isn't trusted blindly",
          "members": ANGLE_CLUSTERS["E"]},
    "F": {"title": "Cross-asset & causality",
          "use": "checks whether the move is really about this ticker or just following peers/news",
          "members": ANGLE_CLUSTERS["F"]},
    "G": {"title": "Validation & attribution",
          "use": "grades the system's own past calls, so confidence is earned, not assumed",
          "members": ANGLE_CLUSTERS["G"]},
}
```

Titles/one-liners are the same ones already produced this session and
in `angle-comprehension-hierarchy/00-explanation.md` -- not invented
fresh here, just made real, importable data instead of only living in
prose. `angle_clusters.py` stays the source of truth for membership;
this module only adds meaning on top, so there's still exactly one
place to update if a cluster's membership ever changes.

### 2. The gatekeeper tool -- deterministic, not an LLM agent

New `vinu-agent/vinu_agent/tools/book_gatekeeper_tool.py`:

```python
class AskTickerBookTool(BaseTool):
    name = "ask_ticker_book"
    description = (
        "Ask what the system currently knows about one ticker, without "
        "needing to already know how that knowledge is organized. The "
        "book has 2 real chapters: 'angles' (glossary, per-ticker angle "
        "data at every real timeframe, 7-cluster synthesis, cross-"
        "cluster analysis) and 'experience' (simulation history, shadow "
        "evaluator -- not yet built, see recording-the-experiece/). "
        "chapter='index' alone lists what's available in both, with no "
        "ticker required. Always includes source_run_id and updated_at "
        "so you can judge how current the read is -- this store holds "
        "the LATEST read only, not a history."
    )
    parameters = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string", "description": "Not required when chapter='index'"},
            "chapter": {"type": "string", "enum": ["index", "angles", "experience"]},
            "sub": {
                "type": "string",
                "description": (
                    "Optional, narrows 'angles' to one sub-chapter: "
                    "'glossary' (1a), 'per_ticker' (1b), 'clusters' (1c, "
                    "optionally further narrowed by `cluster`), "
                    "'cross_cluster' (1d). Omit for all 4."
                ),
            },
            "cluster": {"type": "string", "description": "Optional: one letter A-G to narrow sub='clusters' to just that one"},
        },
        "required": ["chapter"],
    }
    is_readonly = True
    _ticker_summary_store: Any = None  # auto-wired by build_registry(), same pattern trade_plan_tool.py already uses

    def execute(self, **kwargs) -> str: ...
```

Behavior, all deterministic (no LLM call inside):
- `chapter="index"`: returns the 2-chapter/sub-chapter map (titles +
  one-line uses + real member angles for 1c/1d's clusters) -- no
  `ticker` needed, this alone is what lets any agent self-discover what
  it can ask for without reading any other file first. `"experience"`
  is listed here too, marked `"available": false` until
  `recording-the-experiece/`'s plan ships it -- the index stays honest
  about what's real vs. planned.
- `chapter="angles"`: requires `ticker`. Reads `TickerSummaryStore.
  get_summary(ticker)` once, returns the sub-chapter(s) asked for:
  - `sub="glossary"`: `explain_angle`-shaped entries for the angles
    actually present in this ticker's digest (on-demand, not the whole
    28-angle catalog unless asked).
  - `sub="per_ticker"` (1b): `angle_digest` as-is.
  - `sub="clusters"` (1c): `cluster_digest` (+ `cluster_anomalies` for
    the same letters), each entry enriched with its `CLUSTER_INDEX`
    title/use -- fixes the bare-letter gap at the one real place both
    this tool and (separately, see step 3) `forecast_skill` read from.
    `cluster` param narrows to one letter.
  - `sub="cross_cluster"` (1d): the `cross_cluster` field as-is (no
    per-letter enrichment needed, it's ticker-level already).
  - `sub` omitted: all 4 sub-chapters together -- this is what lets
    step 4 below replace `trade_plan_tool.py`'s private logic with a
    call to this tool instead of removing behavior.
- **Each sub-chapter carries its own `available: true/false`**, not just
  a chapter-wide one -- real gap found reviewing this design: a ticker
  can have `angle_digest` populated (1b real) while `cluster_digest` is
  still `{}` (1c/1d not yet run -- e.g. Step 13's `ALL`-format
  comprehension hasn't triggered for it yet). Returning an empty dict
  for 1c in that case would be indistinguishable from "checked, found
  genuinely nothing," which is a different, false claim. Shape:
  ```json
  {
    "ticker": "AAPL", "source_run_id": "...", "updated_at": "...",
    "glossary": {"available": true, "data": {...}},
    "per_ticker": {"available": true, "data": {...}},
    "clusters": {"available": false, "reason": "cluster_digest empty -- comprehension not yet run for this ticker"},
    "cross_cluster": {"available": false, "reason": "..."}
  }
  ```
  `available` for 1b/1c/1d is computed independently (non-empty dict
  after parsing -> true), not inherited from whether the row itself
  exists.
- `chapter="experience"`: returns `{"available": false, "reason":
  "not yet built, see recording-the-experiece/"}` until that folder's
  own plan ships real data here -- a real, named, honestly-empty slot,
  not a silent 404. Once built, follows the same per-sub-chapter
  `available` shape as `chapter="angles"` above (2a/2b each report their
  own availability, not one flag for both).
- Missing store, missing row, or a ticker never comprehended at all:
  `chapter="angles"` itself returns `{"available": false, "reason":
  ...}` at the top level (no row to even attempt sub-chapters against),
  never raises -- same fail-open contract `_read_summary_context`
  already has today.
- `updated_at`/`source_run_id` always included at the top level of the
  response for `chapter="angles"`, regardless of `sub` -- this is a
  ticker-row-level freshness signal, distinct from each sub-chapter's
  own `available` flag.

Registration: automatic via `build_registry()`'s existing `hasattr`
wiring (`_ticker_summary_store` gets injected the same way
`trade_plan_tool.py`'s does today) -- no change needed to
`build_registry()` itself.

### 3. `forecast_skill.py` reads titles from the same index, not a bare letter

`vinu-research/vinu_research/forecast_skill.py:303-311` changes from:

```python
lines.append(f"  Cluster {cluster}: {sentence}")
```

to importing `CLUSTER_INDEX` and rendering:

```python
title = CLUSTER_INDEX.get(cluster, {}).get("title", "")
lines.append(f"  Cluster {cluster} ({title}): {sentence}")
```

Small, deliberately separate from the gatekeeper tool itself -- this is
a different consumer (the forecast prompt-builder, not an
agent-callable tool) reusing the SAME shared index rather than the
gatekeeper duplicating cluster-title logic that forecast_skill also
needs. This is the concrete proof of the "one shared space, not
separate copies" goal: two different consumers, one source of meaning.

### 4. Migrate `trade_plan_tool.py` onto the gatekeeper, don't leave it duplicated

`_read_summary_context` gets replaced with a call to
`AskTickerBookTool(chapter="all")` (constructed the same way any other
tool this file already depends on is constructed) instead of its own
private `store.get_summary` + manual field list. This is the actual
proof this plan achieves its stated goal -- if the one existing
consumer still has its own separate copy of the same logic after this
plan ships, the goal wasn't met.

## Files touched

- **New**: `vinu-agent/vinu_agent/tools/book_index.py`,
  `vinu-agent/vinu_agent/tools/book_gatekeeper_tool.py`, their test
  files.
- **Modified**: `vinu-research/vinu_research/forecast_skill.py` (cluster
  title lookup), `vinu-agent/vinu_agent/tools/trade_plan_tool.py`
  (`_read_summary_context` replaced with a gatekeeper call).
- **Not touched**: `TickerSummaryStore`/`TickerSnapshotStore` schemas
  (no new persistence -- this is a read/routing layer only),
  `angle_clusters.py` (stays the membership source of truth,
  unmodified), `angle_synthesizer`/`cross_cluster_analyst` (they still
  produce the same `cluster_digest`/`cross_cluster` shape, unaware this
  layer exists on top).

## Order

1. `book_index.py` -- pure data, no logic. Test: every letter in
   `ANGLE_CLUSTERS` has a matching `CLUSTER_INDEX` entry (regression
   guard if a cluster is ever added), `members` matches
   `ANGLE_CLUSTERS` exactly (no second source of truth drifting from
   the first).
2. `book_gatekeeper_tool.py`. Tests: each `chapter` value returns the
   right slice, `cluster` narrows correctly, missing-ticker/missing-store
   fails open, `updated_at`/`source_run_id` always present, cluster
   entries are enriched with title/use, each sub-chapter's `available`
   flag is computed independently (e.g. `angle_digest` populated but
   `cluster_digest` empty -> 1b `available: true`, 1c/1d `available:
   false` with a real reason, not silently empty). Run `vinu-agent`'s
   full suite.
3. `forecast_skill.py`'s digest-line change. Test: the rendered line
   includes the real title, not just the letter; falls back gracefully
   if a cluster key isn't in `CLUSTER_INDEX` (defensive, shouldn't
   happen given step 1's regression guard, but this reader shouldn't
   crash if it ever does). Run `vinu-research`'s full suite.
4. `trade_plan_tool.py` migrated onto the gatekeeper. Test: existing
   `trade_plan_tool.py` tests re-run unchanged and still pass (behavior
   parity, not a regression) -- this step should change WHERE the logic
   lives, not what it returns.
5. Run every touched package's full suite once more, all together.

## Verify

- All 4 touched packages' test suites green.
- Manual/documented: call `ask_ticker_book(chapter="index")` (no ticker)
  and confirm it lists both chapters, all 4 "angles" sub-chapters, and
  all 7 clusters with real titles -- zero dependency on any ticker ever
  having been comprehended (pure data), and `"experience"` correctly
  marked `available: false`. Call it with `ticker="AAPL",
  chapter="angles", sub="clusters"` for a real comprehended ticker and
  confirm each entry is labeled with its title, not a bare letter.
  Confirm `trade_plan_tool.py`'s actual trade-plan output is unchanged
  before/after the migration in step 4 (same inputs, same outputs --
  this step moves code, it doesn't change behavior).

## Explicitly deferred, not part of this plan

- Extending `TickerSnapshotStore` to preserve `cluster_digest`/
  `cross_cluster` historically (currently only `angle_digest` is kept
  day-over-day) -- real gap, belongs to `recording-the-experiece/`'s
  plan, not duplicated here.
- Any actual pattern/analogy recognition across past comprehension runs
  -- `recording-the-experiece/problem-explanation.md` already explains
  why that's not safe to build yet (no real historical outcomes to
  validate against).
- Widening the gatekeeper to other teams beyond `screener`/`research`
  (e.g. `risk_gatekeeper`, a future narrating agent) -- the tool is
  general enough to be reused there once those consumers exist, but
  nothing wires it into them yet since none of them currently duplicate
  this logic (only `trade_plan_tool.py` does, per the real evidence
  cited above).
