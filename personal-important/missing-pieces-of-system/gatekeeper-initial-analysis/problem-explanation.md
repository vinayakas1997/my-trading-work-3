# Problem: no gatekeeper in front of the ticker "book"

## Context

`missing-pieces-of-system/angle-comprehension-hierarchy/` already builds
a real, persisted "book" per ticker: Chapter 1 (28-angle index, via
`angle_digest`), Chapter 2 (7 real per-cluster syntheses, via
`cluster_digest`), Chapter 3 (cross-cluster corroboration, via
`cross_cluster`) — all stored in `TickerSummaryStore`
(`vinu-agent/vinu_agent/storage/ticker_summaries.py`) and read back out
by `trade_plan_tool.py::_read_summary_context`. The book itself is real
and working. What's missing is anything that lets another agent, or a
human, ask "what do we know about X for this ticker" and get routed to
the right chapter/section without already knowing the book's internal
shape.

## Confirmed inefficiencies (real, cited)

### 1. A cluster letter carries no meaning where it's actually read

`vinu-research/vinu_research/forecast_skill.py:303-311` builds the
digest line the forecast LLM actually reads as:

```python
lines.append(f"  Cluster {cluster}: {sentence}")
```

Just the bare letter -- `"Cluster A: <sentence>"`. Nothing attaches
what "A" conceptually means ("Classical statistical forecasts") at the
point it's consumed. The mapping exists (`angle_clusters.py`'s
`ANGLE_CLUSTERS` dict, and the cluster titles written out in
`angle-comprehension-hierarchy/00-explanation.md`), but it's never
carried downstream into the actual prompt. A reader (LLM or human) has
to already know the letter-to-meaning mapping from outside the data
itself, or guess.

### 2. Every consumer has to already know the book's structure

`trade_plan_tool.py` reads the entire book (`angle_digest`,
`cluster_digest`, `cross_cluster`, `cluster_anomalies`) unconditionally,
every time, regardless of what it actually needs for the plan at hand.
There's no way for a consumer -- this one, or a future one -- to ask a
narrower question ("what does this ticker's volatility/risk picture
look like") and get routed to just the relevant chapter/cluster. Every
new consumer of ticker knowledge has to re-learn the same internal
shape (which letter means what, which field lives where) from scratch,
by reading this same code, rather than asking something that already
knows.

### 3. No single place answers "what do we actually have for this ticker"

The book's real content is spread across `TickerSummaryStore` (the
current/latest read), `TickerSnapshotStore` (`record_daily_snapshot`,
historical daily snapshots), and `TickerLedgerStore` (the audit trail of
gate decisions, deferrals, forced runs). Nothing today can answer, in
one call, "what do we know about this ticker right now, and how
current/trustworthy is it" without a caller separately querying all
three and already knowing how to interpret each one.

## What this is NOT about

This is not about adding a new LLM delegation. Routing "which chapter
has volatility info" is a deterministic index lookup, not something
requiring reasoning -- the same lesson this project has already learned
twice (the prompt-injection fix, the `get_all_angles` 15x-refetch fix):
a plain instruction doesn't reliably hold against small local models,
only a structural mechanism does. Given the angle-comprehension-
hierarchy design already hasn't finished a full live run with 8
delegations (see that folder's Step 10), adding a 9th LLM agent purely
for routing would add real cost for no corresponding benefit. The fix
here should be a deterministic tool/lookup layer, not another
specialist team member.

## Not yet designed

This file is the problem statement only. The actual gatekeeper design
(the index shape, its lookup interface, which agents would call it, how
it's wired into `build_registry()`) is a separate, not-yet-written plan.
