---
name: phase-1-guard-rail
status: proposed-not-built
purpose: what keeps the recipe-first, sweep-driven loop honest and bounded -- gaming risk, silent data loss, and scope creep this phase must not fall into.
---

# Phase 1 -- Guard rails

**Recipe fit must be justified against real data, not picked to dodge raw
code-gen.** `idea_generator`'s existing grounding discipline ("only treat
an angle as informative if `row_count > 0`," never invent a number)
extends here: if it picks a recipe, the prompt must require it to state
*why* that recipe's shape fits the hypothesis, grounded in the same real
angle/indicator data it already gathered. "Prefer a recipe when one
genuinely fits" is the rule -- not "force a recipe regardless of fit."
Raw code-gen staying available as the exception path is intentional, not
a loophole to close.

**Three different caps exist in this phase -- don't conflate them.**
1. The **round cap** (N rounds) bounds how many times the sweep-refine
   loop narrows and re-sweeps a parameter region.
2. A **grid-size cap**, separate and new, bounds how many points
   `run_parameter_sweep` will run in a *single* round -- without it, a
   combinatorially large parameter grid could make even round 1 expensive
   regardless of the round cap. These are independent limits on different
   things (rounds vs. points-per-round); a fix to one doesn't cover the
   other.
3. (Not this phase's concern, but don't confuse it with the two above:)
   the Planner's outer K-distinct-candidates-per-ticker cap from later
   phases bounds a different loop entirely -- new candidates, not
   refinement of one candidate.

**Completeness's denominator is the requested grid size, not the attempted
one.** If `substitute_param_value` fails to cleanly substitute a parameter
into a recipe for some grid point, that failure must still count against
`completeness` -- it cannot silently reduce the denominator to "how many
points we actually tried" and report 100% of a smaller number. A recipe
that can't be parameterized correctly for part of its grid is exactly the
kind of silent-failure case the completeness field exists to catch.

**Single-voice self-verdict is an accepted, stated limitation of this
phase, not a solved problem.** Role c's PASS/FAIL is one LLM call, not an
adversarial bull/bear pair -- cheaper, but a single voice can rubber-stamp
its own candidate more easily than a debate would. This phase doesn't fix
that; it inherits the design doc's own open question. Don't treat Phase 1
as having silently resolved it.

**No retroactive re-validation.** Artifacts created before this phase
lands (via raw code-gen, no sweep/PBO evidence behind them) keep their
original verdict and provenance as-is. Phase 1 only changes the path for
*new* proposals going forward -- rerunning the sweep engine against every
existing ACTIVE/BENCHING artifact is explicitly out of scope here, not an
oversight.

**New tools are scoped to the `research` team only.** `RunSweepCandidateTool`
and `ListSweepRecipesTool` get added to `teams/research/TEAM.md`'s tool
list specifically, not registered as globally available to every team.
`screener`, `risk_gatekeeper`, and `capital_allocator` have no reason to
see these tools, and giving every team access to every tool is exactly
the kind of scope creep that makes it harder to reason about what an
agent can actually do.
