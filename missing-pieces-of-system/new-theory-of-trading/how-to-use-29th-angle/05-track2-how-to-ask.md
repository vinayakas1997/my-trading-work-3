# Track 2: "how to ask" — the query/summary interface

Mirrors Track 1's proven pattern exactly: a read-only LLM tool
(`get_signal_evidence`, see `01-track1-how-it-works-today.md`) backed by
the same store the recording side writes to, in-process read first, HTTP
fallback second. Track 2's version is `get_move_evidence`.

## The query shapes actually needed, taken directly from the examples given

Three distinct things were asked for, and they map to three distinct
query modes on the same tool rather than three separate tools:

1. **"Tell me 2×–2.5× what was the status"** — a specific checkpoint
   transition, for a symbol or a specific move. Answered by fetching one
   move (`move_id`) and reading its `checkpoints` array, or by asking
   "across this symbol's recorded moves, what did the 2×→2.5× transition
   typically look like" (an aggregate — see "aggregate mode" below).
2. **"Give me the failure thing status, what happened"** — filter by
   `outcome=failed`, returns the failed moves with their (necessarily
   shorter) checkpoint sequences.
3. **"What's the general status for the move in this timing / if it's
   this session"** — filter by `session` (and/or a time range), returns
   moves matching that slice.

## Minimum fields for the request

Following Track 1's own minimalism (its tool takes only `symbol`,
`trigger_id`, `limit` — nothing more was needed):

```
get_move_evidence(
    symbol: str | None = None,        # filter to one ticker
    move_id: str | None = None,       # fetch one full move (all checkpoints), like trigger_id does
    outcome: "extended" | "failed" | None = None,   # filter by outcome
    session: str | None = None,       # 'ny' | 'london' | 'tokyo' | 'overlap' | 'off_hours'
    checkpoint_range: [float, float] | None = None,  # e.g. [2.0, 2.5] -- see below
    limit: int = 50,
)
```

- `checkpoint_range` is the direct answer to "tell me 2×–2.5× what was
  the status": when given, the response includes, for each matching
  move, only the checkpoint(s) whose `atr_multiple` falls in that range
  (plus the rate-of-change into it) — not the whole move's full
  checkpoint list, so the answer stays focused on exactly the transition
  asked about.
- Everything else (`symbol`, `outcome`, `session`) composes as filters,
  same as Track 1's tool.

## Two response modes, same as the question naturally splits

**1. Raw/list mode (default)** — same honesty rule as Track 1's tool:
`{status, symbol, count, extended_count, failed_count, moves: [...]}`,
never a computed statistic, because there's no analysis/bucketing layer
here either (this is deliberately lighter than Phase 3, per
`02-track2-design.md`'s "how this differs from Phase 3" section) — just
honest raw counts and the matching rows.

**2. Aggregate mode** (`aggregate=true` on the same call) — the
`get_move_summary`-style descriptive statistics already named as the
goal in `02-track2-design.md`: "this ticker has had 14 big moves in the
last year, typically building over 8 candles, degrading over 5, usually
preceded by a volume pickup 3-4 candles earlier." Concretely, when
`aggregate=true`:
- counts: total moves, extended vs. failed, per magnitude_bin, per
  duration_bin, per session
- for a given `checkpoint_range`: the average indicator rate-of-change
  into that transition, split extended vs. failed (this is the direct,
  queryable form of Step 5's edge-finding — "at 2×→2.5×, what typically
  differs between moves that kept going and moves that died")

This is still descriptive statistics over recorded raw rows, computed at
query time from `move_events`/`move_checkpoints` — not a precomputed,
stored bucketing table. Same posture as Decision 1: nothing gets
pre-bucketed at recording time, aggregation happens on read.

## Example calls, mapped to the three things asked for

```
get_move_evidence(symbol="AAPL", checkpoint_range=[2.0, 2.5], aggregate=true)
  -> "for AAPL, here's what happens on average as moves cross 2x into 2.5xATR"

get_move_evidence(symbol="AAPL", outcome="failed")
  -> "here are AAPL's moves that touched 2xATR and died before 2.5x"

get_move_evidence(symbol="AAPL", session="ny")
  -> "here are AAPL's recorded moves that happened during the NY session"
```

## What this does NOT do (honesty, same as Track 1)

No win-rate, no expectancy, no position-sizing recommendation comes out
of this tool — that's Phase 3/Layer 4 territory for Track 1, and this is
explicitly a lighter, separate capability for Track 2 (see
`02-track2-design.md`). This tool answers "what happened" and "what's
typical," never "what should I do."

## Still open

- Whether `get_move_evidence` is wired into the same `theory_reviewer`
  agent as `get_signal_evidence`, or a different agent — not decided,
  mirrors the same not-yet-decided architectural-home question in
  `02-track2-design.md`.
- The exact aggregate-mode response shape (field names) — sketched above
  for discussion, not finalized.
