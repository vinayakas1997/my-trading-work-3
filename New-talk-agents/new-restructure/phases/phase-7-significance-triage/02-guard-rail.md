---
name: phase-7-guard-rail
status: proposed-not-built
purpose: what keeps Significance Triage from becoming alert-fatigue noise, keeps it strictly non-blocking, and keeps multi-channel delivery from fragmenting a single flag into confusing duplicate threads.
---

# Phase 7 -- Guard rails

**Significance Triage never blocks anything -- it only informs, after
the fact.** Unlike `risk_gatekeeper` (blocking approval) or the Kill
Switch (blocking execution), the funding decision, the close, or the
rejection this phase surfaces has *already happened* by the time a flag
is raised. This must be explicit in the implementation: a flag with no
human response, ever, does not leave anything pending or unresolved
downstream -- it's a notification, not a gate. Building this as a
synchronous approval step by mistake would silently change every action
it watches into a blocking one, which is not what this phase is for.

**Alert fatigue is a real, specific failure mode -- design against it
from the start, don't discover it in production.** If the significance
threshold is too loose, humans start ignoring flags, which defeats the
entire mechanism. Track, from day one, what fraction of flags actually
get a human response versus going unanswered -- that ratio is the signal
for whether the threshold needs tightening, not a guess. This doesn't
need to be solved in this phase (the exact threshold is one of this
project's stated tuning parameters, same category as `N`/`K`), but the
measurement needs to exist from the start or there's no way to know
later whether it's working.

**Pattern detection (e.g. repeated exposure-driven rejections) must query
`TickerLedger`'s real history, not a separate running counter.** Same
discipline as Phase 6's shared K-cap: one source of truth. A parallel
counter tracking "how many rejections has this ticker had recently"
could drift from what `TickerLedger` actually recorded (e.g. after a
restart, or if an event was written through a path that didn't update
the counter). Query the Ledger directly for the pattern check.

**Multi-channel delivery is one logical notification, not one per
channel.** If both Discord and Telegram are configured, the same
`flag_id` must be referenceable consistently from either channel's
message, and a human's response via *either* channel resolves the same
flag -- not two independent flags each needing their own response. Avoid
building this such that a human who responds in Discord still sees an
unresolved duplicate in Telegram.

**The `source="human_override"` tag follows the same enforced-at-call-site
rule as Phase 6's `source="human"` tag.** No default value on the
`HypothesisRegistry.add_evidence(...)` call this phase makes -- omitting
it must be a hard error, not a silently blank/wrong provenance tag.
