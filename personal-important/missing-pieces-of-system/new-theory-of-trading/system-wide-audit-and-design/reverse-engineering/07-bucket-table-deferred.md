# Point 9: the Layer 4 bucket table — deliberately kept light, not deferred out of laziness

**Status: intentionally not designed in detail.** This is consistent
with, not a gap in, the rest of this design series.

## Why this one point gets different treatment than 2-8

Every other point in this folder got a real schema/API design because
it's buildable now, against data that either already exists or that
this design's own earlier points would start producing. Point 9 is
different: it's the "how much should I trust this" statistical layer —
bucketing recorded trigger rows by supporting-indicator state and
measuring outcome distributions per bucket (`../../00-explanation.md`'s
Layer 4).

`01-planning.md`'s own pending decision log already states this
directly: *"The analysis-layer design (Layer 4)... Deliberately not
decided yet — there's no real accumulated data to test candidate
bucketing methods against until Phase 2 (the recording layer) has been
running for a while."* And confirmed separately:
`01-track1-how-it-works-today.md` — **no real data has actually
accumulated yet**, ever, for the existing `signal_evidence` store (no
`.db` file found under `vinu-components/data/` as of that check).

Designing bucket edges, minimum-sample gating, or cluster-robust
weighting against zero real rows would mean picking a scheme without
anything to validate it against — precisely the bias Decision 1
explicitly warns against locking in prematurely.

## What this means for points 5 and 6 in the meantime

`live_decision_agent` (point 5) and the precondition `tested` flag
(point 6) do **not** block on this. They work off raw evidence —
`get_signal_evidence`/`get_move_evidence`'s honest raw counts, same
posture Track 1/Track 2's own tools already commit to ("never a
computed win rate or statistic"). The agent's `confidence_note` field
(point 5's design) is explicitly qualitative for this same reason, not a
placeholder for a number that's just temporarily missing.

## What would actually unblock point 9

Real accumulated rows in `SignalEvidenceStore`/`MoveEvidenceStore` —
which itself depends on points 2-3 (the live poller + detector) actually
running for a while, live, on real tickers, *plus* the still-open
historical backfill gap (`../02-open-questions-strategy-and-simulation.md`
item #15 — no incremental/rolling backfill exists yet either). Point 9
is downstream of nearly everything else in this folder, which is exactly
why it's last, not first.

## Not abandoned — revisit trigger

Per `01-planning.md`'s own framing: revisit once Phase 2 (recording) has
been running long enough to have real rows to test bucketing schemes
against. Not on a calendar date — on real data volume, the same
"guessed constant vs. real derived value" distinction this whole series
already applies to `FORWARD_HORIZON_BARS`, `floor_multiple`, and the
grace-window length in `03-poller-and-state-schema.md`.
