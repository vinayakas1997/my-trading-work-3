---
name: storage-enhancement-levels-plan
status: decided
purpose: explains how the shared backtest infrastructure (tagging, the walk-forward loop, the weights store, and the query layer) will be built so that all 31 angles in 04-enhancement-of-each-angle/ can use one common, consistent storage system instead of each reinventing its own — written so anyone can read it and understand both what gets built and why, without needing to read code first.
---

# Storage Enhancement — Making Storage Common Across All Angles

## Why this file exists

Every one of the 31 angle files in `04-enhancement-of-each-angle/` describes
a design that's "decided, not yet built." Every single one of those designs
assumes a few pieces of shared machinery already exist — tagging results by
session/day/week/quarter, running a rolling backtest, saving a trained
model's weights, querying aggregated results. None of that machinery exists
as real code yet. This file explains what's being built to fill that gap,
and — just as importantly — the small set of rules every angle must follow
so the result is actually *common* (one system all 31 angles share) instead
of 31 angles each building their own slightly-different version.

This is a design document, like every file in `04-enhancement-of-each-angle/`
— it explains the plan and the reasoning. The actual code comes after.

## What's already decided elsewhere (read this before anything else)

Before designing anything new, three existing project documents were
checked to make sure nothing here contradicts what's already settled:

1. **`00-project-understanding/02-storage-plan.md`** — the original idea:
   results are stored in "tiers." The two that matter here are **Tier 2**
   (a scheduled run, treated as permanent history — once written, it's
   never changed or deleted) and **Tier 3** (a one-off, triggered run,
   allowed to be cleaned up later).
2. **`03-initial-analysis-check-architectural-test/03-actual-plan-findings/03-storage-design.md`**
   — the concrete folder layout for results:
   `{ticker}/{method}/{granularity}/{tier}/{run_id}.parquet`, and the rule
   that "what's the latest result" is always looked up through a proper
   log/database, never by just checking which file on disk is newest
   (checking file dates caused a real double-counting bug once — this
   rule exists specifically to prevent that from happening again).
3. **`.../02-api-design.md`** — how results eventually get served over an
   API: every response carries the same 5 fields (`run_id`, `status`,
   `computed_at`, `tier`, `data`), so any caller can handle any angle's
   result the same way.

**The good news, confirmed by reading the actual code**: the real storage
class already in the codebase (`AngleStorage`, in
`vinu-initial-analysis/vinu_initial_analysis/storage/parquet.py`) already
*is* a working implementation of that decided folder layout and tier rule.
Nothing about the base storage needs to be redesigned. What's missing is
everything that has to happen *around* it — tagging results consistently,
actually running a backtest loop, saving trained models, and querying the
results afterward. Those four missing pieces are what this file covers.

## The four missing pieces, in plain terms

**1. Calendar tagging** — every result needs to know things like "was this
a Wednesday," "which trading session was this in," "which quarter." Right
now nothing computes that automatically — each angle would otherwise have
to reinvent this logic itself, and 31 slightly-different versions of "what
counts as the NY trading session" would inevitably drift apart. One shared
function computes this once, the same way, for every angle.

**2. The walk-forward backtest loop** — nearly every angle's design says
some version of "slide through history, at each point make a forecast
using only what was knowable at that time, check it against what actually
happened next, move forward one step, repeat." That's a generic pattern —
it doesn't need to be written 20 different times for 20 different angles.
One shared loop does the sliding/checking/repeating; each angle only
supplies its own "make one forecast" step.

**3. The weights artifact store** — several angles (DLinear, LSTM,
LPatchTST, PatchTST, TFT, iTransformer, TIPS) retrain a small model from
scratch at every single step of the backtest. Their designs all say the
same thing: save every step's trained model to a file, so any historical
prediction can be traced back to the exact model that produced it. This is
a small, shared save/load convention instead of seven different
almost-identical file-naming schemes.

**4. The query/aggregation layer** — once results are tagged and stored,
someone needs to ask questions like "what's the average accuracy during
the NY session in Q2 2024, and how many data points is that based on."
Every angle's design already insists that answer must always come with its
sample size attached, never just a bare percentage. One shared layer
answers that kind of question consistently for every angle, instead of
each angle writing its own aggregation code (and each one having to
remember, on its own, to always attach the sample size).

## Where each piece lives

| Piece | Lives in | Plain-language reason |
|---|---|---|
| Calendar tagging | `vinu-initial-analysis/vinu_initial_analysis/angles/_tagging.py` | Sits right next to `_market_hours.py`, the file that already has a real, working, already-used session classifier (three angles already depend on it) — this reuses that instead of inventing a second, competing way of deciding what session a timestamp falls in. |
| Walk-forward loop | `vinu-tools/vinu_tools/compute/backtest/walk_forward.py` | `vinu_tools` is this project's established home for shared calculation tools that many angles already import from (risk math, volatility math). The backtest loop is exactly that kind of generic, reusable tool — it doesn't know anything about any specific angle. |
| Weights store | `vinu-initial-analysis/vinu_initial_analysis/storage/weights.py` | Sits next to the existing storage code, since it's really just "one more kind of file this project saves," following the exact same naming/folder conventions already decided for everything else. |
| Query layer | `vinu-initial-analysis/vinu_initial_analysis/storage/query.py` | Also sits next to the existing storage code, since its whole job is reading back what that storage already wrote. |
| Admin/delete helper | `vinu-initial-analysis/vinu_initial_analysis/storage/admin.py` | One function, `delete_angle`, that removes an angle's files from both storage trees *and* its rows from `RunLog` together — see "Deleting an angle cleanly" below for why this needs to exist as its own piece. |

**One wrinkle worth explaining honestly**: the walk-forward loop lives in
`vinu_tools`, but calendar tagging and the weights store live in
`vinu-initial-analysis` — and code in `vinu_tools` isn't allowed to reach
back into `vinu-initial-analysis` (that would create a circular
dependency, the kind of tangled two-way relationship between packages that
makes a codebase harder to reason about over time). The fix: the
walk-forward loop doesn't call tagging or weight-saving directly at all —
it just accepts them as two small functions handed to it when it's
started. Each angle's own small setup file is what actually connects
"here's how to tag a timestamp" and "here's how to save these weights" to
the generic loop. The loop itself stays completely generic and reusable;
only the connecting piece is specific to each angle.

## The rules every angle must follow

This is the actual point of "making storage common" — a shared system
only works if every angle plays by the same rules instead of quietly doing
its own thing. Once the four pieces above exist, every angle's own
backtest code must follow these:

1. **Always tag rows through the shared tagging function** — never
   hand-write session/day/week/quarter logic inside an individual angle.
   *Why:* this is the whole reason 31 angles' results stay comparable to
   each other instead of 31 slightly different definitions of "Wednesday."
2. **Always pass the timeframe explicitly when saving results** — never
   rely on the storage system's default. *Why:* the default exists for
   backward compatibility with older code, and silently relying on it
   would mix a 1-minute backtest's results in with a 1-day backtest's
   results in the same bucket.
3. **Use the "permanent" tier for a real, scheduled backtest; use the
   "temporary" tier only for a genuine one-off test run.** *Why:* mixing
   these up would either clutter the permanent historical record with
   throwaway test runs, or (worse) let a real result quietly get cleaned
   up later as if it were disposable.
4. **Every rate or average a query returns must come with its sample
   size.** *Why:* a 90% success rate based on 2 data points and a 90%
   success rate based on 900 data points are very different claims — this
   rule (already followed by hand in every angle's design doc) is what
   keeps a thin, unreliable slice of data from looking as trustworthy as a
   well-supported one.
5. **When an angle produces multiple values per forecast (e.g. a 5-step
   forecast with a range at each step), store them nested under one row,
   not spread across five separate rows.** *Why:* this was already decided
   angle-by-angle (Chronos, Kronos, lag_llama, iTransformer all do this)
   specifically to avoid repeating the same tags five times per forecast —
   keeping it consistent means the query layer only needs to know how to
   unpack this shape once, not five different ways.
6. **If an angle trains a model at every backtest step, save every
   step's weights — don't skip or sample.** *Why:* the whole point is
   being able to go back and inspect exactly what any historical
   prediction's model looked like; skipping some steps would leave gaps
   in that ability.

## How one angle actually plugs in — a worked example (DLinear)

DLinear is the first angle this gets wired up against, precisely because
its design (`04-enhancement-of-each-angle/05-dlinear.md`) touches every
one of the four pieces: it needs tagging, it runs the walk-forward loop,
it saves weights at every step, and its results need the query layer's
aggregation. Once built, the shape of DLinear's own small setup file looks
like this (illustrative — the real file comes after the four shared pieces
exist):

```python
# angles/dlinear/backtest.py — DLinear's own glue code, nothing generic lives here
from vinu_tools.compute.backtest.walk_forward import run_walk_forward
from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.storage.weights import WeightsStore

def dlinear_step(step):
    # train DLinear's tiny model fresh on step.history, forecast one step ahead,
    # compare against step.future — this part is 100% DLinear-specific
    ...
    return StepResult(row={...}, weights=model.state_dict())

def run_dlinear_backtest(symbol, timeframe, bars, data_root):
    weights_store = WeightsStore(data_root)
    # NOTE: weights_store.save() needs (symbol, angle_name, timeframe, bar_ts,
    # weights) — but the generic harness only ever calls weights_sink with
    # (symbol, timeframe, bar_ts, weights), since the harness itself has no
    # concept of "angle_name" (it's generic infrastructure, reused by all 31
    # angles). DLinear's own glue code is what knows its own name, so it's
    # DLinear's job to close over "dlinear" here — passing weights_store.save
    # directly, unwrapped, would call it with the wrong arguments and break
    # immediately. This small wrapper is what every angle's glue file needs.
    def _save_weights(symbol, timeframe, bar_ts, weights):
        return weights_store.save(symbol, "dlinear", timeframe, bar_ts, weights)

    return run_walk_forward(
        symbol, timeframe, bars, dlinear_step,
        min_observations=100,
        tag_fn=tag_row,
        weights_sink=_save_weights,
    )
```

Everything DLinear-specific (how it trains, what it forecasts, what
counts as a "hit") lives in `dlinear_step`. Everything generic (sliding
the window, tagging every row the same way, saving weights the same way)
comes from the shared pieces. Every other angle's own setup file follows
this exact same shape — only the "step" function's internals change, and
each one writes its own tiny `_save_weights` wrapper with its own angle
name baked in, the same way DLinear's does above.

## Where results actually get stored (concrete paths)

Two separate things get written to disk, in two separate places under the
same configured data root (`data_root`, the one folder everything in this
project already lives under):

**1. Backtest result rows** — go through the existing `AngleStorage`,
unchanged. Verified directly from its code, the real, full path a DLinear
backtest result actually lands at is:

```
{data_root}/analysis/{symbol}/{angle_name}/{granularity}/{tier}/{run_id}.parquet

e.g. {data_root}/analysis/AAPL/dlinear/1D/tier2/a1b2c3d4e5f6.parquet
```

**2. Trained model weights** — go through the new weights store (piece 3),
in its own sibling top-level folder, sharded by year/month so one folder
never holds hundreds of thousands of files (see "Deeper rationale" below):

```
{data_root}/weights/{symbol}/{angle_name}/{timeframe}/{YYYY}/{YYYYMM}/{bar_ts}.pt

e.g. {data_root}/weights/AAPL/dlinear/1D/2024/202405/1715779800.pt
```

**One detail that matters for correctness**: `WeightsStore.save(...)`
returns that **entire path string** (everything after `{data_root}/weights/`)
as the `weights_ref` value stored on the result row — not just the bare
`{bar_ts}.pt` filename. That's deliberate: it means `weights_ref` alone is
enough to find and reload that exact model later
(`WeightsStore.load(weights_ref)`), without also having to separately
remember which symbol/angle/timeframe/month it came from. If `weights_ref`
were only the filename, reloading it later would require passing all four
of those back in from outside — which defeats the point of storing a
single, self-contained reference on the row in the first place.

## Deleting an angle cleanly

The flip side of "easy to add an angle" is "easy to remove one" — if an
angle later turns out not worth keeping (several already have, per the
`04-enhancement-of-each-angle/` verdicts), removing it should not leave
storage in a half-cleaned state.

Checked directly against the real code: `AngleStorage.list_angles()` and
`list_symbols()` work purely by scanning folders, so nothing there goes
stale — but `RunLog` (`storage/meta.py`) is a separate SQLite table with
no delete method at all. Deleting an angle's parquet/weight files without
also removing its `runs` rows would leave `get_latest_run()` pointing at a
`run_id` whose file no longer exists — a silent dangling reference, the
same category of bug the SQL-log-not-mtime rule was already introduced to
prevent.

**Fix, added as a fifth small piece**: `storage/admin.py`, sibling to
`weights.py`/`query.py`, with one function:

```python
def delete_angle(data_root: str, angle_name: str) -> None:
    """Removes {symbol}/{angle_name}/ under analysis/, weights/, and
    _multi/*/{angle_name}/, for every symbol — then deletes every matching
    row from RunLog. One call, not three manual steps to remember."""
```

Because both storage trees already key by `{symbol}/{angle_name}/...`
this can't be a single directory removal — but it can, and should, be a
single function call that gets every symbol and both trees and the SQL
log in one atomic-in-intent sweep, instead of leaving that as a manual
checklist someone eventually forgets a step of.

**One known limitation, not a blocker today**: `WeightsStore.save()`
takes a single `symbol` string, matching how all 7 angles that currently
train per-step models (DLinear, LSTM, LPatchTST, PatchTST, TFT,
iTransformer, TIPS) are single-symbol. `cross_attention_gcn_news_price_fusion`
is multi-ticker but — confirmed from its own design doc — has no real
training loop yet (random, never-updated weights), so it doesn't need the
weights store today. If its future multi-ticker training work ever lands,
`weights.py` will need a ticker-set/hash variant mirroring
`AngleStorage`'s existing `_multi/{ticker_hash}/` pattern — worth naming
now so it isn't a surprise later, not worth building for a training loop
that doesn't exist yet.

## Deeper rationale

**Why DLinear is the first angle this gets proven against, not a more
"important" one like ARIMA or Chronos:** DLinear's own design doc touches
all four shared pieces and is cheap and fast to run (a model with under
1,000 parameters, well under a second per step) — that makes it the
fastest way to find bugs in the shared plumbing itself. ARIMA's own design
doc already flags its own compute cost as unmeasured and possibly
expensive; debugging shared infrastructure against something that slow
would make every fix cycle painfully slow. Once DLinear proves the
pipeline works end to end, ARIMA (which adds a different hit-definition
style) and then a foundation-model angle like Chronos or lag_llama (which
adds the nested multi-step result shape) get wired up next, before the
remaining angles.

**Why the weights store shards files by year/month instead of one flat
folder:** DLinear's own design doc says every single walk-forward step's
weights get saved — across a full multi-year, 1-minute-resolution
backtest, that's on the order of hundreds of thousands of small files for
one symbol alone. A single flat folder with that many files becomes slow
to list and awkward to back up. Splitting into year/month subfolders keeps
each individual folder a reasonable size.

**Why results are tagged the same way `_market_hours.py` already
classifies sessions, instead of the four-region (Tokyo/London/New York/
Sydney) scheme described in `common-rule-of-time-slicing-tags.md`:** that
four-region scheme was designed with crypto/FX symbols in mind, which
this project doesn't trade yet — and this project already has a working,
already-relied-upon session classifier tuned specifically for the US
equity market it actually analyzes. Using the real, working, already-used
classifier is a genuine choice, not an oversight; the broader scheme
becomes relevant later if crypto or FX symbols are ever added, and can be
revisited then, since the four-region doc explicitly names that as its own
trigger condition.

## Related files

- `04-enhancement-of-each-angle/00-plan-and-status.md` — the index of all
  31 angle designs that assume this infrastructure exists.
- `04-enhancement-of-each-angle/common-rule-of-time-slicing-tags.md` — the
  original tagging concept this plan implements a working version of.
- `03-initial-analysis-check-architectural-test/03-actual-plan-findings/03-storage-design.md` —
  the storage layout this plan builds on top of, not around.
- `03-initial-analysis-check-architectural-test/03-actual-plan-findings/02-api-design.md` —
  the API contract (`run_id`/`tier`/response envelope) this plan stays
  consistent with.
