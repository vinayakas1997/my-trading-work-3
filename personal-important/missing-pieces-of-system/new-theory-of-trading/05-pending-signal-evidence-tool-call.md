# Expose signal-evidence via a tool call

**Priority: high.**
**Status: done (2026-09-24) -- read-only tool built, tested, and wired
into theory_reviewer. See "What was built" at the end of this file.**

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

## What was built (2026-09-24)

The three open questions above were resolved as follows, all matching
the file's own default recommendations:

- **Read-only, as recommended.** `GetSignalEvidenceTool`
  (`vinu-agent/vinu_agent/tools/signal_evidence_tool.py`) only reads --
  no write path. `is_readonly = True`. Writing new trigger rows stays
  exclusively the `signal_evidence` angle's job, so the look-ahead-bias
  risk noted above never gets reopened.
- **Wired into `theory_reviewer`** (`thesis_intake` team) only, for now
  -- the closest existing analog (it already reviews a submitted theory
  against `query_hypotheses`' evidence trail; checking
  `get_signal_evidence` for a theory built around the SMA(5)/SMA(50)
  cross is the same pattern applied to this new evidence source). Its
  `prompt.md` gained an explicit step: if the theory resembles that must-
  condition, call the tool and weigh the real recorded trigger count/
  outcomes -- but treat `count=0` as "nothing recorded yet," never as
  evidence against the theory. Other teams (screener, summary) are a
  deliberate, separate future decision, not wired by default.
- **Interface**: `symbol` (optional -- filters to one ticker),
  `trigger_id` (optional -- fetches one event's full indicator snapshot
  instead of the summary list), `limit` (optional, default 50). The
  summary-list path returns exactly what this doc predicted it should:
  `{count, outcomes_recorded, triggers}` -- honest raw counts, no
  computed win rate or statistic, since Phase 3's analysis layer still
  doesn't exist.

**Implementation shape**: not quite `ticker_summary_tool.py` after all --
the actual closest analog turned out to be `query_hypotheses_tool.py`,
since `SignalEvidenceStore` lives in `vinu-research` (a separate
service), same as `HypothesisRegistry`. Follows that exact pattern: try
an in-process read first via a new `vinu_agent/broker/research_link.py`
getter (`get_signal_evidence_store()`, added alongside its existing
`get_hypothesis_registry()`/`get_strategy_store()` siblings, same
`_research_data_root() / "<db>.db"` construction `ResearchService`
itself uses), falling back to HTTP against `GET /research/signal-
evidence[/{trigger_id}]` on any exception (missing package, service not
reachable, etc.).

**Tests**: `vinu-agent/tests/test_signal_evidence_tool.py`, 11 tests
mirroring `test_query_hypotheses_tool.py`'s structure -- in-process
list/filter/outcome-counting/not-found behavior against a real temp
`SignalEvidenceStore`, plus HTTP-fallback tests (correct URL/params,
404-as-not-found, error propagation). All passing.

**Sandbox gap fixed, not just noted**: this sandbox was missing the
`tenacity` package (a real declared dependency,
`vinu-infra/pyproject.toml` line 15: `tenacity>=8.2` -- just not
installed in this environment), which had blocked
`test_generate_tool_catalog.py` and `test_phase6_thesis_intake_scoping.py`
before this change and was initially only worked around (verified
indirectly via YAML-parsing and reading test logic, see prior version of
this note). Installed `tenacity` (`pip install tenacity`, resolved to
9.1.4, satisfies the `>=8.2` constraint) and re-ran both previously-
blocked files for real: **7/7 passed**, including
`test_discovers_real_tools_with_expected_shape` (confirms
`build_registry()`'s real auto-discovery actually finds
`GetSignalEvidenceTool`, not just that the module parses) and
`test_theory_reviewer_has_the_real_evidence_tools` (confirms the real
scoped registry, not just the YAML file). Also confirmed directly:
`get_signal_evidence` appears in `build_registry()`'s real tool-name
list.
