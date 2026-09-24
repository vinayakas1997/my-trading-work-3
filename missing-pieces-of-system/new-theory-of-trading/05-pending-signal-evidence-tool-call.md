# Pending: expose signal-evidence via a tool call

**Priority: high.**
**Status: not started -- planning only.**

**Note on scope, stated up front**: the request that produced this file
was "the signal evidence is there, we can use the tool call [for it]" --
read here as: rather than (or in addition to) only being reachable via
raw HTTP (`/research/signal-evidence/...`, already built and tested),
expose it as a proper `BaseTool` in `vinu-agent`'s existing LLM
tool-call framework (`vinu_agent/agent/tools.py` -- `execute()` +
`to_openai_schema()`, the same shape `book_gatekeeper_tool.py` and
friends already use), so an LLM agent (screener, summary, planner) can
query or trigger it directly during a real agent run, not just a human
or a script hitting the HTTP route by hand. If that's not what was
meant, correct this file's scope before building anything from it.

## What already exists (real, tested, ready to be wrapped)

- `vinu-research`'s HTTP routes (`routes_signal_evidence.py`):
  `POST .../trigger`, `POST .../{trigger_id}/outcome`,
  `GET .../{trigger_id}`, `GET .../?symbol=...`.
- `vinu-initial-analysis`'s `signal_evidence` angle (#29) already
  produces trigger+outcome data automatically for any ticker the
  screener discovers, via the existing angle pipeline.

## What a tool wrapper would need to decide

- **Read-only or read/write?** A read-only tool (`GET .../{trigger_id}`,
  `GET .../?symbol=...` wrapped as "look up recorded evidence for this
  ticker") is low-risk and immediately useful for an LLM agent that
  wants to reason about a ticker's history during a screener/summary
  pass. A write-capable tool (letting an LLM directly call
  `POST .../trigger`) is a much bigger decision -- it would mean an LLM
  can inject evidence rows outside the angle pipeline's own, already-
  validated point-in-time computation, reopening exactly the
  look-ahead-bias risk Decision 10 was careful to avoid. Default
  recommendation: read-only tool first; a write path, if ever needed,
  is a separate, later decision made deliberately, not a side effect of
  building the read tool.
- **Which agent(s) get it?** `vinu-agent`'s tool registry is per-team
  (screener, summary, planner, etc. each have their own tool set,
  going by the existing `book_gatekeeper_tool.py`/`ticker_summary_tool.py`
  naming pattern) -- worth deciding which team(s) actually have a real
  use for querying signal-evidence before wiring it into all of them
  by default.
- **What does the LLM actually ask for?** A raw `trigger_id` lookup is
  not a natural thing for an LLM to know to ask for. The tool's real
  interface is more likely "give me a summary of this ticker's recorded
  must-condition history" (a `symbol`-scoped query, already supported by
  `GET .../?symbol=...`), possibly with a human-readable summary layer
  on top (win rate so far, sample count) rather than raw JSON rows --
  though that summary layer overlaps with Phase 3's still-deferred
  analysis layer, so a v1 tool should probably just surface the raw
  count/list honestly (`N triggers recorded, M with outcomes filled in`)
  rather than trying to compute real statistics before Phase 3 exists.

## Suggested next step (not started)

Confirm the read-only-first scope, then add a new tool file in
`vinu-agent/vinu_agent/tools/` (e.g. `signal_evidence_tool.py`) following
the exact shape of an existing simple tool (`ticker_summary_tool.py` is
probably the closest analog -- a thin HTTP-calling wrapper around an
existing route, not new business logic), calling `vinu-research`'s
already-built `GET /research/signal-evidence` route.
