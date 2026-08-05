---
name: storage-plan
status: discussion-phase
purpose: the storage-planning discussion for the vinu project — the five storage tiers, the core design principle, and the open design questions to settle. Pure design discussion, no implementation.
---

# Storage Plan — Discussion Notes

> **Note to the reader:** while reviewing this file, do not worry about or think
> about the stage-2 (live trading) and stage-3 (during-trading / post-trade)
> things. They are mentioned below for **information only** — to give the full
> picture of where stage 1 sits. Everything in this file that matters, and
> everything the user refers to, is about **stage 1 (the pre-analysis stage)**.

## The five storage tiers (conceptual)

**Tier 1 — Raw data (append-only, unbounded)**
- News: accumulates forever, never rewritten
- Price: accumulates forever, never rewritten
- One principle: analysis never modifies this layer

**Tier 2 — Quarterly full pre-analysis (fixed start, rolling end)**
- Runs 4×/year at Q1→Q4 boundaries
- Start date never changes → every ticker analyzed over the same `[start, Qn]` window
- This is what preserves cross-ticker comparability
- Output is a *frozen snapshot* — once Q1 closes, it's history

**Tier 3 — Triggered pre-analysis (same window shape)**
- Same `[start, now]`, but fired when a new strategy/analysis arrives
- Must be distinguishable from scheduled Tier-2 runs in the log
- Together, Tiers 2+3 complete the "pre-analysis" stage

**Tier 4 — Live decision (stage 2 — information only)**
- Inputs: frozen pre-analysis snapshots (Tier 2/3) + live news/price + light initial analysis
- Output: a *decision snapshot* — which pre-analysis runs, which live-data window, which plan
- This is what makes a later claim traceable ("the plan cited the Q2 run, not Q1")

**Tier 5 — Trade record + analysis (stage 3 — information only)**
- Trade details (fills, positions, exits)
- Trade analysis (predicted vs actual, what went wrong, debrief)

## The core design principle this rests on

**Immutability of closed periods.** The moment Q1 ends, its analysis is frozen. It
becomes *evidence* for later decisions — and evidence that changes retroactively is
worthless. The design's whole strength is that Q2's agent can trust "Q1's report is
stable."

## The design questions that must be settled (discussion, not code)

1. **Quarter boundary semantics** — is the boundary *calendar* (Apr 1, Jul 1…) or
   *sliding* (every 90 days from start)? "Start date doesn't change" suggests
   calendar-aligned from the initial start. Which?

2. **What exactly freezes at quarter end** — only the final report? Or also the
   intermediate parquet/run data? The argument is *all of it* freezes, because
   stage 2 needs the underlying evidence, not just the summary.

3. **Retention** — how long do frozen quarterly snapshots live? Forever (all
   years), or a rolling N quarters? This decides whether storage grows unbounded.

4. **Triggered runs (Tier 3) and comparability** — if a strategy arrives
   mid-quarter and triggers a run, does it *invalidate* the quarterly snapshot, or
   coexist as a separate tagged run? The argument is coexist — the quarterly series
   must stay clean.

5. **The stage-2 decision snapshot** — what's the minimum it must record so a later
   claim is verifiable? (Which pre-analysis runs it used + which live window + the
   plan + the expected outcome.) *Note: this is stage-2, information only here.*

6. **Cross-ticker consistency** — the point about "retaining consistency" — does
   every ticker get the *same* quarterly run even if added mid-quarter, or only
   tickers present from the start?

## Related files

- `project-explanation.md` (same folder) — the project picture, phases, and goals
- `differnt-combination-analysis.md` (same folder) — the combination matrix
