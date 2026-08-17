---
name: phase-8-guard-rail
status: proposed-not-built
purpose: what keeps both additions from quietly undoing the Summary Agent's existing grounding discipline -- the thing that made it survive the original real-LLM test.
---

# Phase 8 -- Guard rails

**Consensus checks need a third outcome: insufficient data, not just
agree/diverge.** If either angle in a comparison has `row_count == 0`,
the correct output is "can't compare, insufficient data" -- never forced
into "agree" or "diverge." Silently treating missing data as either
would directly violate the grounding discipline this whole team is built
on (never invent a number, and "no data" is meaningfully different from
"data that happens to agree").

**Calibration downweighting and missing data must stay visibly distinct
reasons, never merged into one vague "don't trust this angle."** An angle
with real data (`row_count > 0`) but a poor historical calibration score
is still real data -- the Summary Agent should say so explicitly ("this
angle has data but has underperformed historically"), not omit the angle
the same way it would omit one with no data at all. If both cases end up
looking the same in the output, a reader can no longer tell "nothing to
report" from "something to report, cautiously."

**The categorical-adjacency table belongs in a companion config file, not
embedded in the prompt.** Same pattern as `skills/strategy-tags/tags.yaml`
-- which regime/lifecycle labels count as "adjacent enough to agree" is a
judgment call that will need tuning as more angle pairs get added. A
config file can be corrected without redeploying the prompt; logic
embedded in prose can't be reviewed or diffed the same way.

**Every consensus/divergence claim must cite the specific real values
compared, not an impression.** Same "cite specific numbers" discipline
`angle_synthesizer`'s prompt already enforces for individual angles --
extending it to comparisons matters just as much, since "these two angles
disagree" is a new kind of claim this phase introduces, and it's exactly
the shape of claim that's easy to state confidently without actually
checking the two real values against each other.
