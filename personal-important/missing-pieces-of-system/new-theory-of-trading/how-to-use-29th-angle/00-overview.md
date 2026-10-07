# Overview: the 29th angle, and the two tracks it now covers

This folder exists because the 29th angle (`signal_evidence`) started as
one thing (Decision 10 of `../01-planning.md`: a must-condition trigger
recorder) and is now growing a second, genuinely different capability
next to it (Track 2: strategy-agnostic big-move recording). Both live
under the same "29th angle" umbrella conceptually, but they are not the
same mechanism, and this folder's job is to explain each clearly, with
nothing left out, and to be explicit about what's real/implemented today
versus what's still just a settled design waiting to be built.

## Track 1 — must-condition triggered recording (real, implemented, tested)

**Status: fully built and verified.** See
`01-track1-how-it-works-today.md` for the complete explanation: what it
records, the real schema, the real HTTP API, and how to actually query
it today.

In one sentence: when a specific condition fires (today, the running
example is SMA(5) crossing above SMA(50)), the system snapshots 52 real
supporting-indicator values at that instant and records the eventual
outcome, building an evidence table that answers "given this exact
condition and these indicator readings, what actually happened
historically."

## Track 2 — strategy-agnostic big-move recording (designed, not yet built)

**Status: design settled in this conversation, not yet implemented.**
See `02-track2-design.md` for the full explanation and
`03-move-detection-threshold-options.md` for the specific open decision
on how "a big move" gets defined numerically.

In one sentence: instead of starting from a condition and asking "what
happens after," Track 2 starts from a real, already-happened big price
move (detected from pure price action, no strategy or condition
involved) and records its full anatomy — what the market looked like
before it started, during it, and as it degraded/reversed — building a
library of real move behavior that can later inform which conditions
(must-conditions for Track 1) are actually worth building around, rather
than guessing one and hoping.

## Why both exist together

Track 1 needs a condition to already exist before it can record
anything. Track 2 needs no condition at all — it only needs a real,
detectable move to have happened. That makes them complementary in a
specific direction: Track 2's recorded evidence (what precedes a real
big move) is exactly the kind of research material that should inform
which must-condition Track 1 ends up using, rather than Track 1 starting
from an arbitrary, hand-picked example (SMA5×SMA50) forever.

## Files in this folder

- `00-overview.md` — this file.
- `01-track1-how-it-works-today.md` — the real, implemented Track 1
  mechanism: schema, API, how to query it, what's actually stored.
- `02-track2-design.md` — the full Track 2 design: detection, the
  pre/during/post recording structure, the indicator-differentiation
  methodology, magnitude/duration binning, session/day-of-week tagging.
- `03-move-detection-threshold-options.md` — how "big move" gets defined
  numerically (decided: ATR-multiple, 2×ATR floor), with the trade-offs
  against the two alternatives (return z-score, rolling percentile) laid
  out for the record.
- `04-track2-engine-and-storage.md` — where the detection engine lives
  (`vinu_tools`, shared with the future live detector), the full storage
  schema (`MoveEvidenceStore`, mirroring `SignalEvidenceStore`'s
  pattern), and the config knobs for PRE/DURING/POST window lengths.
- `05-track2-how-to-ask.md` — the query/summary tool design
  (`get_move_evidence`), mirroring `get_signal_evidence`'s pattern.

**This folder deliberately stops at the 29th angle itself (Track 1 and
Track 2).** Everything that grew beyond that scope — the full system
layer map, the strategy-definition schema, and the full system-wide
audit findings across all 6 layers — moved to a sibling folder,
`../system-wide-audit-and-design/`, so this folder stays focused and
readable as just "how the 29th angle works," without mixing in the much
larger system-wide picture. See that folder's own `00-overview.md` for
what's there.
