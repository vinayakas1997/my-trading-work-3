# Points 5 + 6 designed: the deciding agent, the tool it needs, and precondition tracking

**Status: design-only, nothing built.** Checked directly against real
code (2026-09-25) — `vinu-agent`'s existing tool/agent pattern, applied
here rather than invented fresh.

## Why these two together

Point 6 (precondition `defined`/`tested` tracking) only means anything
once something real flips `tested: false -> true` at the moment it
actually checks. That something is point 5's agent. Same reasoning as
why points 2+4 were designed together.

## Part A — the tool: `get_live_decision_context`

### The existing pattern, confirmed real

`vinu-agent/vinu_agent/tools/signal_evidence_tool.py` is the model to
copy, not reinvent:

- Subclasses `BaseTool` (`..agent.tools.BaseTool`), sets `name`,
  `description`, `parameters` (JSON schema), `is_readonly = True`.
- `execute(**kwargs) -> str` (a JSON string), tries an **in-process
  store read first** (`get_signal_evidence_store()` in
  `broker/research_link.py`), falls back to HTTP on any failure.
- Response is always **honest raw data** — "never a computed win rate or
  statistic, because Phase 3 doesn't exist" (its own docstring, line
  11-24) — the same honesty rule this whole design series holds to.

### The new tool, same shape

```
get_live_decision_context(
    ticker: str,
    strategy_id: str,
)
```

Returns, in one call (so the agent doesn't need 3 separate round-trips
to assemble its own context):

```json
{
  "status": "ok",
  "ticker": "...",
  "strategy_id": "...",
  "stage": "fired_awaiting_confirmation",   // from strategy_stage_state (point 4)
  "trigger_id": "...",
  "live_snapshot": { "adx": 17.8, "rsi": 61.2, ... },  // point 3's output
  "precondition": {
    "description": "...",                   // from the strategy's own definition
    "defined": true,
    "tested": false                         // this call is what would flip it (Part B)
  },
  "signal_evidence_summary": {              // get_signal_evidence's own shape, embedded
    "count": 34, "outcomes_recorded": 31, "triggers": [...]
  }
}
```

**Why one combined tool instead of the agent calling
`get_signal_evidence` + a new state-lookup + a new snapshot-lookup
separately**: the existing `get_signal_evidence`/`get_move_evidence`
tools are correctly scoped to their own store (Track 1/2's evidence).
This new tool's job is different — it's the live "what does this
specific pending decision look like right now" assembly, which needs
data from three real sources (`strategy_stage_state`, point 3's live
snapshot, and a call into the existing evidence store). Composing it
server-side means the deciding agent gets a complete picture in one
call, same reasoning `01-track1-how-it-works-today.md` already gives for
why Track 1's own tool bundles trigger + indicators + outcome into one
response instead of three.

**Implementation shape**: same in-process-first, HTTP-fallback pattern.
The in-process path reads `strategy_stage_state` and `live_snapshots`
directly (wherever those end up living per point 8's architectural
decision), and calls the *existing* `get_signal_evidence_store()`/
`get_move_evidence` internally rather than re-implementing evidence
lookup — reuse, not a second evidence-reading path.

## Part B — the agent

### The existing pattern, confirmed real

`teams/thesis_intake/agents/theory_reviewer/AGENT.md`:

```yaml
---
name: theory_reviewer
role: theory-reviewer
prompt_file: prompt.md
depends_on: []
tools: [get_all_angles, get_ticker_summary, query_hypotheses, get_signal_evidence, ...]
skills: [thesis-intake-strategy-definitions, thesis-intake-risk-rules]
---
```

A plain markdown frontmatter block naming its tools by the same `name`
string each `BaseTool` subclass declares. Notably: `theory_reviewer`
**cannot write or execute code** — no `run_backtest` or similar in its
tool list, enforced "by omission, not a prompt instruction" (its own
AGENT.md line 17-19). This is a real, already-used safety pattern worth
reusing deliberately for the new agent too.

### The new agent: `live_decision_agent`

```yaml
---
name: live_decision_agent
role: live-decision-maker
prompt_file: prompt.md
depends_on: []
tools: [get_live_decision_context, get_signal_evidence, get_move_evidence]
skills: []   # tbd -- see "what this leaves open"
---
```

**Deliberately no execution tool in this list either** — same
"structurally cannot act, only decide" posture as `theory_reviewer`.
This agent's output is a **decision recommendation**, not a placed
order. Point 7 already established why: even a correct decision from
this agent still has to pass through `vinu-live`'s own risk-limit check
before anything real happens — this agent deciding "act" and something
else actually acting are two different steps, and keeping this agent
tool-restricted from execution enforces that split the same way
`theory_reviewer`'s restriction enforces "reviews, doesn't backtest."

**What it does, concretely**: called once a `strategy_stage_state` row
transitions to `ready_to_execute` (point 4's terminal pre-decision
state). Calls `get_live_decision_context(ticker, strategy_id)`, reads
the precondition description + live snapshot + historical evidence, and
produces a decision:

```json
{
  "decision": "execute" | "skip" | "extend_grace_window",
  "reasoning": "...",
  "precondition_held": true,
  "confidence_note": "..."   // honest, since Layer 4's bucket table (point 9)
                              // doesn't exist yet -- this is qualitative,
                              // not a computed confidence score, until point 9 exists
}
```

**`precondition_held` is what flips point 6's `tested` flag** — see Part
C.

## Part C — precondition `defined`/`tested`, concretely wired now

`03-strategy-definition-full-schema.md` item 4 already proposes the
field shape:

```
precondition: { description: "...", defined: true, tested: false }
```

Previously this was just a schema proposal with no real writer. Now
there's one: **every time `live_decision_agent` returns a decision for a
given `(ticker, strategy_id, trigger_id)`, that's a real check against
real evidence** — the precondition's `tested` flag flips to `true`
(regardless of whether the decision was "execute" or "skip" — being
checked and failing is still being tested), and `precondition_held`
records the outcome of that specific check.

**Confirmed against real code where this field would have to live**:
`vinu-strategy/vinu_strategy/models/strategy.py:13-16`'s
`_KNOWN_TOP_LEVEL_KEYS` is a hardcoded frozenset (`name`, `description`,
`schedule`, `features_required`, `correlation_required`,
`angles_required`, `pipeline`, `universe`, `metadata`) — `precondition`
is not in it today. Adding the field to a strategy's YAML/JSON
definition alone does nothing (same warning item #22.4 already gave for
`must_conditions`/`risk_management`) — it needs adding to this frozenset
*and* a real write-back path from the agent's decision into wherever
that strategy's stored definition lives, not just a schema addition.

## What this leaves open

- The agent's `prompt.md` content (what reasoning instructions it gets)
  — not written here, needs its own pass once the tool/data shapes above
  are settled and real.
- Whether this agent runs as an LLM call per `ready_to_execute` event
  (potentially expensive at scale — many tickers, many strategies) or a
  cheaper rule-based first pass with LLM escalation only for ambiguous
  cases — a real cost/latency design question, not decided.
- The write-back path for `tested`/`precondition_held` into the
  strategy's stored definition — which store, what API — not decided,
  same open status `03-strategy-definition-full-schema.md`'s own
  "what this deliberately does NOT try to solve" section already flags.
- Whether `skills: []` should include something — `theory_reviewer`
  uses `thesis-intake-strategy-definitions`/`thesis-intake-risk-rules`;
  whether this new agent needs equivalent live-decision-specific skills
  isn't decided.
