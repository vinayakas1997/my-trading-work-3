# Why 55 → 25 → 6: the reverse-engineering chain behind the maturity-agentic system

## Context

This is the conceptual "why" behind the design worked out in
`missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/`
(see `00-decided-pattern.md` for the full 9-step narrative and worked
example, `agents-implementation-plan.md` for the build order). This doc
exists separately because the *shape* of the reasoning — why 6 analysts,
why they don't map one-to-one onto trading performance, why the chain
runs 55 → 25 → 6 and not some other structure — is worth stating
plainly, on its own, without the schema/implementation detail around it.

Like everything else this folder describes: **design, not
implementation.** Nothing here has been built.

## The chain, in order

**55 raw data points** — already being written today, scattered across
every package in the system (vinu-agent, vinu-research, vinu-portfolio,
vinu-live, vinu-screener, vinu-stock-price, vinu-initial-analysis):
LLM call logs, calibration history, position books, ingest logs, risk
checks, screener rankings, the earnings calendar, and more. Cataloged in
full in `project-understanding/05-full-recorded-information/README.md`.
Today, each package only ever reads its own tables — nothing joins
across them.

**25 analytical points** — concrete questions, each one just a join
across 2+ of those 55 stores that nobody currently reads together: does
a shaky LLM call predict a bad decision, does the screener's rank
actually predict anything, do trades held through earnings lose more.
No new instrumentation needed anywhere — every signal these questions
need already exists, just unjoined.

**6 analysts** — not an arbitrary grouping. The 25 analyses cluster
naturally by *the kind of question they answer*, and those clusters
land almost exactly on the system's own existing package boundaries:

1. **Forecast Intelligence** — how good are our forecasts, and why
2. **Regime & Risk Coverage** — where are the blind spots, where is risk quietly building
3. **Execution & Money-Flow** — why do we actually lose money, mechanically
4. **Decision-Process / Cognition** — is our own reasoning process actually good
5. **Governance & Freshness** — is our own bureaucracy helping or hurting
6. **External-Signal Cross-Check** — do our other independent systems agree with the main pipeline

## The part worth being explicit about: this isn't just a trading-signal layer

Only **3 of the 6** analysts (Forecast Intelligence, Regime & Risk
Coverage, Execution & Money-Flow) are directly about market/trading
quality. The other **3** — Decision-Process, Governance & Freshness,
External-Signal Cross-Check — are the system reflecting on **itself**:
its own cognition, its own internal discipline, its own consistency
across independently-built parts. That's the actual reason this is
called a *maturity* system rather than another trading-signal module —
the six analysts together produce a profile of how much the system
currently understands about **its own behavior**, not only about the
market it's trading in.

None of the six analysts are LLM teams — each is a small, deterministic
module (same category as `trade_score_calibration.py`'s existing
calibration functions already in this codebase), running on a
schedule, joining real tables, and writing a structured finding only
when something actually crosses a significance threshold. The one LLM
seat in the whole design sits *above* all six — a single synthesis
agent (the "brain," step 8 of `00-decided-pattern.md`) that reads across
all six clusters and notices when two separate findings are actually
one story. It can only ever suggest; it never executes a trade or
touches the kill switch.

## Summary

```
55 raw stores  →  25 cross-package analyses  →  6 analysts (clustered by question-type)
   (data                (joins nobody              (3 trading-quality,
    already exists)      currently makes)            3 self-reflection)
```

The system doesn't just get better at predicting the market through
this chain — it gets a structured, evidence-gated way to know how much
it currently understands about itself, across six independent axes,
before it lets any of that self-knowledge influence a real decision.
