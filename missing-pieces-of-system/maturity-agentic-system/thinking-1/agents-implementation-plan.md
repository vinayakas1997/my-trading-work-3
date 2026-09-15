# Agents implementation plan: 6 analysts + 1 brain

## Context

This is the concrete follow-through on two earlier docs in this folder:

- `data-driven-analysis-opportunities.md` — the 21 cross-package
  analyses (A–U) that are buildable today with zero new instrumentation,
  because every signal they need is already being written to one of the
  55 stores cataloged in `project-understanding/05-full-recorded-information/README.md`.
- `../maturity-agentic-system-explanation.md` — the original
  `MaturityAssessor` design (one deterministic module, zero-to-one LLM
  calls, no agent hierarchy).

This doc answers the question that came next in conversation: **given
21 analyses, how many agentic pieces does this actually need, how do
they relate to each other, and what does "maturity" become once they
exist?** It also lays out a concrete build order — not just the shape,
but the sequence.

## The headline shape: 6 analyst modules + 1 brain, not 21 and not 1

Grouping the 21 analyses by *the kind of question they answer* produces
six natural clusters — and those clusters land almost exactly on the
system's own existing package boundaries, which is a strong signal
they're the right seams rather than an arbitrary split.

| # | Analyst | Answers | Owns (from A–U) | Primary source packages |
|---|---|---|---|---|
| 1 | **Forecast Intelligence** | How good are our forecasts, and why | A, Q, P, G, S | vinu-research, vinu-initial-analysis, vinu-stock-price |
| 2 | **Regime & Risk Coverage** | Where are the blind spots, where is risk quietly building | B, E, N | vinu-research, vinu-live, vinu-portfolio |
| 3 | **Execution & Money-Flow** | Why do we actually lose money, mechanically | C, U | vinu-infra, vinu-live |
| 4 | **Decision-Process / Cognition** | Is our own reasoning process actually good | D, L, K, M | vinu-agent, vinu-infra |
| 5 | **Governance & Freshness** | Is our own bureaucracy helping or hurting | O, R, F | vinu-agent |
| 6 | **External-Signal Cross-Check** | Do our other independent systems agree with the main pipeline | I, J, T | vinu-screener, vinu-live |

Each analyst is **not an LLM team** — it is the same category of thing
`MaturityAssessor` already is: a deterministic module, same shape as
`trade_score_calibration.py`'s calibration functions, that runs on a
schedule, joins/aggregates real tables it's scoped to, and writes a
structured finding. No LLM is needed to notice "angle X's Brier score
has degraded three windows running" — that's the identical "count real
rows, check against a threshold" logic already proven in four places in
this codebase (see the vision doc's "why this isn't a new idea" section).

## Layer 0: a shared finding schema, before anything else is built

All six analysts should write to the same shape, in the same store
pattern every other SQLite store in this system already uses
(`vinu_infra.sqlite.SQLiteBackend` — WAL mode, thread-local connections,
`SCHEMA_VERSION` + `MIGRATIONS`). One new table, e.g. `reflection_findings`:

```
finding_id PK, analyst_name, cluster, computed_at,
signal_json (JSON — the real numbers: counts, ratios, deltas),
evidence_count (INTEGER — how many real rows backed this finding),
severity (routine | notable | significant),
narrative TEXT NULL (optional, only if that analyst's finding warrants
  a one-line human-readable gloss — still no LLM required to write this;
  a templated string off signal_json covers most cases)
```

The `evidence_count` field is load-bearing, not decorative — it's what
lets the brain (Layer 2 below) refuse to synthesize a confident
narrative out of a finding backed by 4 samples the same way it would one
backed by 400. This is the same discipline `trade_score_calibration.py`
already applies locally, made a queryable field instead of a private
threshold buried in one function.

## Layer 1: the 6 analysts, in build order

Each analyst is a plain module + a scheduler entry, same shape as the
existing `skill-audit-worker` (3600s cadence). None of these need to run
per-decision — daily or weekly is the right cadence, since none of the
underlying source data changes faster than that in a way worth
re-synthesizing more often.

**Recommended build order** (highest leverage / lowest risk first, per
`data-driven-analysis-opportunities.md`'s closing section):

1. **Decision-Process / Cognition** (owns D) — start here specifically
   because `llm_calls.db` and `telemetry.db` are fully-built,
   fully-written, zero-reader stores today. This is a pure read + join,
   no new writer needed anywhere, the fastest possible first proof that
   the pattern works end-to-end.
2. **External-Signal Cross-Check** (owns I) — the lowest-risk way to
   decide whether `vinu-screener` is worth formally integrating, using
   data both sides already produce independently.
3. **Regime & Risk Coverage** (owns B) — the most direct upgrade over a
   single maturity scalar: tells a consumer agent exactly *where* to be
   cautious, not just how much, closest to the original `MaturityAssessor`
   intent.
4. **Forecast Intelligence** (owns A, plus S as a free add-on check) —
   largest cluster, most moving parts (angle × regime × ticker
   cross-tab), build after 1–3 have proven the finding-schema pattern.
5. **Execution & Money-Flow**, **Governance & Freshness** — round these
   out last; both are real but lower-urgency than the four above.

## Layer 2: the brain — one synthesis agent, not a hierarchy

Above the six analysts sits **one** agent that reads the latest
`reflection_findings` rows across all six clusters (plus
`MaturityAssessor`'s existing scalar tier, if that's built in parallel)
and does the thing no deterministic analyst can do alone: notice when
two findings from *different* clusters are actually one story. Example:
Forecast Intelligence flags a decaying angle in the same window Regime
Coverage flags thin evidence in that angle's best regime — that's one
insight, not two, and only a synthesizing read across both catches it.

This is the Layer-2 "single synthesis call" already scoped in
`maturity-agentic-system-explanation.md`, just fed six structured inputs
instead of one. One prompt, structured findings in, one synthesized
read out — not a team, not a debate pattern.

### Authority boundary — the part that must not slip

- **Can**: surface findings to Planner / `risk_gatekeeper` /
  `capital_allocator` / Significance Triage; propose bounded threshold
  nudges through the exact same sample-gated, human-approved mechanism
  `trade_score_calibration.py` already uses.
- **Cannot**: place an order, touch the Kill Switch, or change a
  threshold directly. The only enforcement point stays `OrderGuard` /
  the real filesystem Kill Switch, unchanged. A synthesis agent that
  could bypass that would be a regression from the current architecture,
  not an upgrade — it would be the one thing in this system that
  *acts* on unproven belief instead of proposing from it.

### Do not build a second brain

The already-planned narrating agent (`missing-pieces-of-system/narating-agents/`)
was explicitly decided to be a single agent, not a team, doing exactly
this kind of cross-cutting synthesis to decide "how aggressively should
I trade, given what the system currently knows." That is the same seat.
**Recommendation: the System Reflection brain and the narrating agent
should be the same agent**, not two agents independently synthesizing
the same picture — building both would recreate exactly the
"two copies of the truth" risk `maturity-agentic-system-explanation.md`
already flagged as the failure mode to avoid for the DB itself.

This needs to be confirmed against `narating-agents/narrating-agent-explanation.md`'s
actual content before being locked in — flagged here as an open item,
not assumed.

## What "maturity" becomes once this exists

The original design collapsed everything into one label
(`cold_start → paper_only → early_live → mature`). Once the six
analysts exist, that collapse is no longer necessary — each analyst
*is* a dimension of maturity, not an input pre-flattened into one
number:

- Forecast Intelligence → maturity of **forecasting**
- Regime & Risk Coverage → maturity of the **risk-map**
- Execution & Money-Flow → maturity of **execution understanding**
- Decision-Process → maturity of **reasoning itself**
- Governance & Freshness → maturity of **self-discipline**
- External-Signal Cross-Check → maturity of **corroboration**

The brain holds a **maturity profile**, not a maturity point. A system
can be `mature` on execution and `cold_start` on regime coverage for one
strategy family at the same time — a materially more honest and more
actionable thing for `risk_gatekeeper` to read than one global word.
Existing consumers each read the *specific axis* relevant to their own
decision, not the whole profile every time — the same "one more input"
integration already scoped for Planner / `risk_gatekeeper` /
`capital_allocator` in the original maturity doc, just pointed at the
right axis instead of the one scalar.

## The recursive rule: the brain must earn trust in itself, too

Every existing calibration mechanism in this codebase refuses to trust
a number until real evidence backs it. That discipline has to apply to
the brain *about its own synthesis*, not only about the tickers and
strategies it's judging:

1. Each analyst's finding already carries `evidence_count` (Layer 0) —
   the brain must not synthesize a confident combined narrative out of
   findings where the evidence counts are lopsided (three findings
   backed by hundreds of real rows, three backed by a handful).
2. The brain's own synthesized judgments need their own track record
   before they're trusted much — same `min_paper_days`-shaped gate
   Shadow's promotion gate already uses for a strategy artifact, applied
   this time to the brain's own narrative output. Concretely: log each
   synthesis alongside what it predicted, and require a minimum sample
   of synthesis-then-observed-outcome pairs before letting the brain's
   narrative carry as much weight as the six analysts feeding it.

This is the same caveat already written into `hindsight-memory-harness-explanation.md`:
don't let Opinion-network confidence outrun what's actually been earned
— applied here to the brain's confidence about itself.

## Build order, end to end

1. **Confirm the merge** — read `narating-agents/narrating-agent-explanation.md`
   in full; decide definitively whether the brain and the narrating
   agent are one agent (recommended) or two.
2. **Layer 0** — build `reflection_findings` (or equivalent), the shared
   schema every analyst writes to, `SQLiteBackend`-based like everything
   else.
3. **Layer 1, analysts 1–2** — Decision-Process (owns D) and
   External-Signal Cross-Check (owns I) first: zero new writers needed,
   fastest proof the pattern works end to end.
4. **Layer 1, analysts 3–6** — Regime & Risk Coverage, Forecast
   Intelligence, then Execution & Money-Flow / Governance & Freshness,
   in that order.
5. **Layer 2** — build the single synthesis agent (or extend the
   narrating agent, per step 1's answer) to read across all six
   clusters' latest findings and `MaturityAssessor`'s tier.
6. **Wire consumers** — Planner's forecast prompt, `risk_gatekeeper`'s
   portfolio-fit bar, `capital_allocator`'s `reserve_fraction`, each
   reading the specific maturity axis relevant to their decision.
7. **Recursive self-trust tracking** — log the brain's own synthesis
   predictions against later observed outcomes, gate how much weight its
   narrative carries by its own accumulated sample size.

## Scope note

This is a plan, not an implementation — nothing described here has been
built. Every step above should get the same schema/query-level scoping
`maturity-agentic-system-explanation.md` §3 did for `MaturityAssessor`
before being built, one analyst at a time, in the order above.
