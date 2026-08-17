---
name: phase-7-plan
status: proposed-not-built
purpose: deep-dive plan for Phase 7 -- Significance Triage, new, distinct from the existing passive digest reader. Comes after Phase 5 on purpose, since it needs real Monitor/capital_allocator/risk_gatekeeper output to have anything to triage.
---

# Phase 7 -- Significance Triage

## Why this comes after Phase 5, not before

Significance Triage judges which autonomous decisions are routine (skip)
versus unusual enough to surface to a human now. It's fed by
`capital_allocator` (Phase 2), Monitor (Phase 5's extension of
`TradePlanOrchestrator`), and `risk_gatekeeper`'s `REJECTED` verdicts.
None of that real output exists to triage until those phases have landed
-- this is why the critical path in the 9-phase build order runs
`0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 7`, skipping straight from 5 to 7.

## What already exists, and why it isn't this

`vinu_agent/audit/research_digest.py` is real, but purely passive -- it
replays a stored summary the next time a symbol happens to come up in
conversation. It doesn't decide anything is worth surfacing; it just
answers "what happened here" if asked. Significance Triage is the
opposite shape: it actively decides, unprompted, whether something
warrants surfacing now, without waiting to be asked.

## What this phase builds

**1. The triage judgment itself.** A new team/stage that receives events
from three sources -- `capital_allocator`'s funding/rebalance-request
decisions, Monitor's decay/close outcomes, and `risk_gatekeeper`'s
`REJECTED` verdicts -- and classifies each as routine (no human action
needed) or significant (surface it). "Significant" isn't a single rule;
real candidates include: a repeated pattern of exposure-driven rejections
for the same ticker (worth a human seeing "we keep hitting limits here"),
an unusually large single funding decision, or a position closing for a
reason that contradicts the original thesis strongly enough to be
surprising rather than expected decay.

**2. The delivery path -- reuse, don't build a new one.** Per the earlier
architectural review of this project's real HTTP surface: vinu-agent
already has working Discord/Telegram channel wiring
(`vinu_agent/channels/discord.py`, `telegram.py`, started inside
`server/app.py`'s `_lifespan`). Significant flags get pushed through
those existing channels -- **do not** build a new polling endpoint
(`GET /agent/flags`) that nobody's actively watching. A human who isn't
already in the Discord/Telegram loop wouldn't see a new endpoint either;
reusing the channel that already reaches them is both less work and
actually effective.

**3. Each flag gets an id.** A `flag_id` (same `uuid.uuid4().hex[:12]`
convention as everywhere else) so a human's reply can reference which
flag they're responding to -- this id becomes the `ref_id` on the
eventual `HypothesisRegistry` write when the human responds.

**4. Closing the loop back.** Whatever a human decides in response gets
written through `HypothesisRegistry.add_evidence(...)` -- the same
method Monitor's Phase 5 write already uses -- tagged
`source="human_override"`. The Planner's mandatory pre-proposal consult
then sees a human's correction exactly like any other recorded outcome,
with the flag's `flag_id` as `ref_id` linking back to what prompted it.
Without this, a human's correction is invisible to the next pass and the
same pattern can get flagged (or proposed) again as if nobody weighed in.
