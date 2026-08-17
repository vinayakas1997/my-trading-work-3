---
name: common-rule-of-time-slicing-tags
status: decided
purpose: shared tagging rule for time-based slicing of any angle's backtest results — decided once here, reused by every angle file instead of re-deciding per angle.
---

# Common Rule — Time Slicing Tags

## Example (what a tagged result row looks like)

Every stored forecast row from any angle's walk-forward backtest gets these
extra tag columns attached, on top of whatever that angle already outputs
(forecast, confidence_interval, hit, etc.):

| symbol | timeframe | candle_ts (UTC)       | hit | session | day_of_week | week_of_month | month | quarter |
|--------|-----------|------------------------|-----|---------|-------------|----------------|-------|---------|
| AAPL   | 1D        | 2024-05-15T13:30:00Z    | 1   | ny      | Wednesday   | 3              | May   | Q2      |

That's the target shape. Everything below explains how each tag column gets
its value.

## Example (what a queryable aggregate key looks like)

Once rows are tagged, the tags combine into a human-readable, queryable key
that maps to an aggregated metric plus its sample count:

```
NY-PREMARKET-0800-1330-1MIN = 85%   (n=1,204 forecasts)
```

See "Aggregate key format" and "Storage layers" below for how these keys
get built and stored.

## Why tag instead of just storing counts

Tagging = labeling each individual result row with which bucket it belongs
to. Counting/aggregating (e.g. "Wednesday: 85% hit-rate") is a separate,
later step done by grouping the tagged rows.

Storing only the counts loses the raw rows, which means you can no longer
slice by a *combination* of tags later (e.g. "Wednesday AND ny session AND
Q2") without rerunning the backtest. Keeping every row tagged means you can
re-aggregate any way you want, any number of times, without recomputing
anything.

## Base timezone: UTC

Alpaca provides candle timestamps in UTC. All tagging rules below are
defined directly in UTC — no timezone conversion happens anywhere. This
means a session boundary like "Tokyo session" always refers to the same
fixed UTC window regardless of where the data originated or where anyone
viewing the results is located. No ambiguity, no conversion step to get
wrong.

## Tag 1 — Session

Four global sessions, each defined as a fixed UTC hour range:

| Session | UTC hours |
|---|---|
| Tokyo (Asian) | 00:00 – 09:00 |
| London | 08:00 – 17:00 |
| New York | 13:00 – 22:00 |
| Sydney | 22:00 – 07:00 |

A candle's `candle_ts` (UTC) is checked against these ranges to assign its
session tag. Ranges overlap by design (e.g. London/NY 13:00-17:00 UTC is
the highest-volume overlap window) — a candle can be tagged into more than
one session if it falls in an overlap.

Note: these are the global FX/crypto-style sessions. For a pure US-listed
equity symbol (most of what Alpaca serves), real trading activity mostly
only happens in the NY window plus its own pre-market/regular/post-market
sub-windows — Tokyo/London/Asian tags will mostly show "market closed" for
such a symbol. The 4-session tag becomes fully useful once crypto or FX
symbols (true 24/7 markets) are added.

## Tag 2 — Day of week

Standard Monday–Friday tagging, taken directly from `candle_ts`. No special
holiday handling beyond what's naturally reflected by the absence of
candles on non-trading days.

## Tag 3 — Week of month

Which week of the calendar month the candle falls in (1st, 2nd, 3rd, 4th,
5th week), taken from `candle_ts`.

## Tag 4 — Month

Calendar month, taken from `candle_ts`.

## Tag 5 — Quarter

Calendar quarter (Q1 = Jan–Mar, Q2 = Apr–Jun, Q3 = Jul–Sep, Q4 = Oct–Dec),
taken from `candle_ts`.

## When tags get computed

Tags are computed once, at result-storage time (when the backtest writes
each forecast row), and stored as extra columns alongside the row — not
recomputed on the fly at analysis time. This keeps later slicing/group-by
queries cheap, at the cost of needing to re-tag stored history if a bucket
definition (e.g. session UTC ranges) ever changes.

## Aggregate key format

Individual tags (Tags 1-5 above) combine into a single, self-explanatory
key string for querying aggregated results:

```
{SESSION}-{SUBSESSION}-{UTC_START}-{UTC_END}-{TIMEFRAME} = hit_rate%
```

Examples:

```
NY-PREMARKET-0800-1330-1MIN = 85%
NY-MARKETHOURS-1330-2000-1MIN = 78%
LONDON-REGULAR-0800-1700-15MIN = 81%
```

The key is readable on its own — no lookup needed to know which UTC window
and timeframe it represents.

**Caution — don't bake every dimension into one fixed mega-key.** Combining
session + subsession + day-of-week + week + month + quarter + timeframe all
at once shrinks sample sizes fast; some combinations may only have a
handful of forecasts, which isn't statistically meaningful. Keys should be
built with only as many dimensions as the query actually needs — see
"Storage layers" below for how shallow (common) vs. deep (custom) keys are
handled differently. Every returned key must carry its sample count `n`
alongside the metric, so a thin/unreliable result is visible rather than
silently trusted.

## Storage layers

Three layers work together, from raw data to fast lookup to flexible
on-demand querying:

**Layer 1 — Raw tagged rows (source of truth).** Every individual
forecast, fully tagged per row as shown in the example table above. Never
changes once written; everything else derives from this.

**Layer 2 — Precomputed common keys (fast lookup).** After each backtest
run, precompute and store the common/default aggregate keys — session +
subsession + timeframe, the combinations that get queried often. Each
stored key carries its `n` (sample count) alongside the metric, e.g.
`NY-PREMARKET-0800-1330-1MIN = 85% (n=1,204)`. This avoids recomputing from
raw rows on every lookup for the queries that matter most.

**Layer 3 — On-demand query service (composable, on the fly).** A
service that builds any custom key combination at query time by reading
directly from Layer 1 — for anything not already sitting in Layer 2 (e.g.
adding day-of-week or quarter on top of the default key). Not one fixed
mega-key stored permanently; keys are composed only when asked for, and
every result still returns its `n` so thin slices are visible rather than
silently trusted.

```
NY-PREMARKET-1MIN = 85%                    (Layer 2, precomputed)
NY-PREMARKET-1MIN-Wednesday = 82%          (Layer 3, on-demand, thinner n)
NY-PREMARKET-1MIN-Wednesday-Q2 = ??%       (Layer 3, on-demand, likely too thin to trust)
```

## Scope

This tagging rule is common across all angles — decided once here rather
than re-decided inside each of the 31 per-angle files. Any angle's backtest
results get tagged the same way before being stored.
