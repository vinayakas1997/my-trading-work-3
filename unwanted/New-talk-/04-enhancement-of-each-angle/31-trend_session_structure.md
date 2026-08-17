---
name: angle-31-trend_session_structure
status: decided
purpose: discussion and enhancement proposal for the `trend_session_structure` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_session_structure/`.
---

# 31 — trend_session_structure

**Title (from spec.yaml):** Trend Session Structure

## 1) Status

- Discussed: 2026-08-08
- Status: decided (design settled, not yet built)
- Reference implementation verified against real code: `compute.py` /
  `sessions.py` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/trend_session_structure/`.
- Not a forecaster, not a pretrained/fallback situation — a session-level
  aggregation layer over `trend_lifecycle`'s (angle 30) already-stored
  peak/trough snapshots.
- **Genuinely well-built, verified directly — the cleanest angle
  reviewed in this pass, no bugs found.**
  - **Correctly avoids duplicating `trend_lifecycle`'s peak detection**:
    reads `trend_lifecycle`'s stored output directly ("Option A: single
    source of truth" per the code's own comment) — the opposite of the
    independently-reimplemented-detection problem already flagged
    between `shock_clustering`/`shock_personality`.
  - **Correct deduplication**: keeps the latest stored row per
    `(inflection_type, bar_ts)`, so a snapshot recaptured later with a
    finalized (mature) outcome correctly replaces its earlier immature
    version instead of double-counting both.
  - **Correct thin-sample handling, already matching this project's own
    standard**: rates/averages are suppressed (`None`) for any session
    below `_MIN_SAMPLE = 10` mature peaks (or `_MIN_MATCHES_FOR_SIMILARITY
    = 5` for similarity), while raw counts are always reported — exactly
    the "always show n, never let a thin slice masquerade as signal"
    discipline this project has had to *add* to several other angles;
    here it was already present.
  - **Correct scope boundary**: returns `not_applicable` for 1D+
    timeframes instead of computing a session breakdown that would be an
    artifact (every daily+ bar lands in one session bucket) — an honest
    status, not a silently-wrong number.
- **One deliberate divergence from the shared tagging rule, worth naming
  explicitly rather than leaving unexplained**: this angle uses its own
  4-category session scheme (`premarket / regular / afterhours /
  closed`) — a US-equity-market-hours taxonomy — instead of
  [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)'s
  global FX-style sessions (Tokyo/London/NY/Sydney). This is the right
  choice for this specific angle: that shared file itself notes the
  global sessions "mostly show market closed" for pure US-listed
  equities and only become fully useful once crypto/FX symbols are
  added — the premarket/regular/afterhours split is the taxonomy that
  actually matches what this angle is analyzing. Not a bug, not fixed to
  match the shared rule, kept as its own considered choice.
- Shared/common piece: does **not** use
  [common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)'s
  session definitions (see above); the day/week/month/quarter tags from
  that file don't apply either, since this angle's output is already a
  cross-time, per-session aggregate, not a per-timestamp row.

## 2) One-line definition

Trend Session Structure takes the peaks and troughs `trend_lifecycle`
already found and asks a narrower question of the same data: does
premarket, regular-hours, or afterhours trading tend to produce the
"real" tops — the ones with bigger drawdowns, faster recoveries, or
stronger historical-pattern matches — reported honestly with sample
counts so a session with too little data never gets treated as if it
had a real answer.

## 3) Decided parameters

| Parameter | Decided value | Notes |
|---|---|---|
| Data source | `trend_lifecycle`'s stored snapshots and matches, read directly (code default, kept as-is) | no duplicated detection logic — already correct |
| Session taxonomy | `premarket / regular / afterhours / closed` (code default, kept as-is) | deliberately different from the shared global-session tagging rule — see §1 |
| Min sample floor | 10 mature peaks per session before reporting rates/averages (code default, kept as-is) | already correct, no change |
| Min matches for similarity | 5 (code default, kept as-is) | already correct, no change |
| Timeframes | 1min, 5min, 15min, 1H, 4H — widened to include the two finer intraday formats; **1D still excluded, not widened** | the 1min/5min widening follows the standard update applied across every angle. 1D stays `not_applicable` for a structural reason, not a compute-cost one: a 1D bar's timestamp sits at midnight UTC and never falls inside any real trading session, so a session breakdown for 1D+ bars is a meaningless artifact, not just thinner data — independently confirmed empirically during `05-dlinear`'s real-data validation (`06-implementation-of-each-angles/05-dlinear/02-real-scenario.md`, finding: all 1D rows show `session="closed"`) |
| **Proposed: extend once `trend_lifecycle`'s signal-outcome backtest exists** | add a per-session breakdown of the new confidence-calibration/signal-accuracy data proposed in `30-trend_lifecycle.md` (§3) — does stated confidence actually track real accuracy differently by session | the one natural, dependent addition — this angle already exists specifically to ask "does session matter" of `trend_lifecycle`'s data, so it's the natural home for that same question applied to the new signal-outcome data once it's built |
| Symbol scope | parameterized — specific ticker | matches code's real interface |
| Date range | 2022-01-01 → 2026-Q2 | same as other angles |

## 4) Example — what results look like

**Existing output (unchanged, already correct):**

```
session: regular
n_peaks: 84
n_mature_peaks: 62
meets_floor: true
avg_drawdown_pct: -6.8
median_drawdown_pct: -5.1
worst_drawdown_pct: -22.4
recovery_rate: 0.71
avg_recovery_bars: 9.2
avg_similarity: 0.79
n_matches: 41
```

```
session: closed
n_peaks: 3
n_mature_peaks: 2
meets_floor: false
avg_drawdown_pct: null
```

(Thin session honestly reported as not meeting the floor, not silently
given a misleading average from 2 data points.)

**Proposed addition, once `trend_lifecycle`'s backtest exists:**

```
session: regular
n_signals: 47
avg_stated_confidence: 0.74
measured_success_rate: 0.68
```

## 5) Storage, querying, API shape

No change to the existing design — it already reads directly from
`trend_lifecycle`'s storage and computes its aggregate on demand, which
is the right shape for this kind of derived, session-sliced summary. The
one proposed addition (§3) slots into the same existing per-session row
shape, no new storage architecture needed.

## 6) What we will achieve / how to use it

- Confirmation that this angle is already sound — no correctness work
  needed, unlike most other angles reviewed in this pass.
- Once built alongside `trend_lifecycle`'s proposed backtest, a genuine
  answer to whether this system's signal reliability varies by session —
  a natural, low-cost extension of a pattern this angle already
  implements correctly for drawdown/recovery/similarity.

## 7) Deeper rationale

**Why so little changes here compared to almost every other angle
reviewed:** the code is already doing the things this whole discussion
process has been pushing other angles toward — thin-sample suppression,
no duplicated detection logic, honest "not applicable" instead of a
fabricated number. There's no correctness gap to close, so the design
discussion is appropriately short rather than padded out to match other
angles' length.

**Why the session-taxonomy divergence is documented rather than
"fixed" to match the shared rule:** applying the global Tokyo/London/NY/
Sydney sessions here would make the output *less* useful, not more
consistent — this angle's whole subject is intraday equity-market
structure, where premarket/regular/afterhours is the taxonomy that
actually carries meaning. Consistency for its own sake isn't the goal;
matching the right tool to the actual question is.

**Why the one proposed addition is conditional on `trend_lifecycle`'s
own change:** there's nothing to break down by session until the
signal-outcome backtest proposed there actually produces data — this
isn't a new idea invented here, it's the natural consequence of that
upstream angle's own addition, surfaced through the session lens this
angle already provides for everything else.

**Open/unresolved:** none beyond what's already flagged in
`30-trend_lifecycle.md` — this angle's own design has no open questions.
