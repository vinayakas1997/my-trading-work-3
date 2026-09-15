# Hindsight-ai: the memory-harness reference

The one canonical explanation of **Hindsight** (`vectorize-io/hindsight`)
as the memory harness for this system's maturity-aware agents — its real
API, its four memory networks, and the one known reliability caveat.

Any future consumer that needs a memory harness (a narrating/self-
evaluating agent, a research loop with cross-run memory, or anything
else that reads/writes belief-with-confidence over time) should build on
what's described here rather than re-deriving Hindsight's API from
scratch — and its own beliefs should be gated by the maturity tier
described in `maturity-agentic-system-explanation.md`, in this same
folder: don't let Hindsight's Opinion-network confidence outrun what the
system has actually earned the right to believe.

## Sources (verified 2026-09-14, via live web search — not from memory/training data)

- [vectorize-io/hindsight](https://github.com/vectorize-io/hindsight) — main repo, MIT license, ~23.6k stars
- [Hindsight docs](https://hindsight.vectorize.io)
- [hindsight-client on PyPI](https://pypi.org/project/hindsight-client/) — `pip install hindsight-client`, latest version 0.8.4 (Jul 2026)
- [hindsight_client.py source](https://github.com/vectorize-io/hindsight/blob/main/hindsight-clients/python/hindsight_client/hindsight_client.py) — read directly to verify real method signatures
- [Introducing Hindsight (Vectorize blog)](https://vectorize.io/blog/introducing-hindsight-agent-memory-that-works-like-human-memory)
- [Hindsight is 20/20 (arXiv paper)](https://arxiv.org/html/2512.12818v1)
- [Memory Banks API](https://hindsight.vectorize.io/0.8/developer/api/memory-banks), [Ingest Data / retain](https://hindsight.vectorize.io/developer/api/retain)
- [Issue #4378](https://github.com/vectorize-io/hindsight/issues/4378) — the reliability caveat below

Everything below that describes Hindsight's actual API was checked against the real client source file above, not assumed. Where an earlier third-party summary got a detail wrong, that's called out explicitly (see "Corrections" at the bottom) — don't trust that summary over what's in this file.

## Why Hindsight, not a general-purpose store like mem0

The deciding factor, raised directly in conversation: a system whose
memory grows for months needs old memories to *consolidate* into durable
beliefs, not just accumulate as an ever-growing flat log that recall has
to re-read in full every time. mem0 (dual vector+knowledge-graph,
~7K tokens/retrieval, ~48K GitHub stars, YC-backed) was considered and
rejected specifically because it doesn't do this tiered
retain-then-consolidate step — it's a good general-purpose memory store,
just not built for "don't let memory degrade as it grows."

## What Hindsight actually is

Hindsight is a real, actively maintained agent memory system, distinct
from a vector-DB/RAG approach. Its stated design goal is agents that
*learn*, not just *recall*.

**Three core operations** (verified against the real client source):

| Operation | What it does | Real method |
|---|---|---|
| **Retain** | Extracts facts/entities/temporal data from content you give it and stores them | `aretain(bank_id, content, timestamp=None, context=None, tags=None, ...)` |
| **Recall** | Searches memory — combines semantic, keyword, graph, and temporal retrieval, then reranks | `arecall(bank_id, query, tags=None, tags_match=..., temporal_window=None, budget="mid", ...)` |
| **Reflect** | Reasons over retained memory to synthesize an answer, shaped by the bank's configured "disposition" | `areflect(bank_id, query, budget="low", tags=None, apply_all_directives=False, ...)` |

**Four memory networks** inside a bank:
- **World** — objective facts (e.g. "SPY realized 22% drawdown in the 2022 rate-hike regime").
- **Experience** — the agent's own past actions (e.g. "I backtested a 20/50 MA crossover on AAPL, got Sharpe 0.8, failed holdout").
- **Opinion** — subjective beliefs with a confidence score, formed by reflecting over experience+world facts (e.g. "momentum tends to fail on AAPL in high-vol regimes" — 0.72 confidence).
- **Observation** — consolidated mental models derived by reflecting across many facts/experiences.

**Why it fits the "don't let memory degrade as it grows" need**: `retain`
uses an LLM to extract facts/entities/temporal data from each new memory,
then automatically **consolidates related facts into "observations"** —
deduplicated, evidence-grounded beliefs the bank builds up across many raw
entries, either automatically after retain/update/delete, or only when
explicitly triggered via a `consolidate` endpoint. Separately, `reflect`
does a deeper pass over everything in the bank relevant to a query,
forming new connections that get persisted as opinions/observations,
"including temporal reasoning about which facts are current." This is the
mechanism behind any "daily → weekly → monthly rollup" idea: raw
entries get retained one at a time, and consolidation/reflect turn the
pile into durable, higher-level beliefs — instead of every recall having
to re-read an ever-growing flat log.

**Temporal grounding is built in, not bolted on**: `retain` accepts a
`timestamp`, `recall` accepts a `temporal_window` and `query_timestamp`.
This is the "when did this hold true" dimension a plain vector-search
memory doesn't give you — critical for a trading system, where "momentum
works on AAPL" is only true under some regimes, not all of them.

**A bank has a configurable disposition** (`acreate_bank`'s real
parameters: `mission`, `disposition_skepticism`, `disposition_literalism`,
`disposition_empathy`, or a combined `disposition` dict, plus
`reflect_mission`, `retain_mission`, `background`) — this shapes how
`reflect` reasons, e.g. a highly skeptical disposition demands more
evidence before forming a confident opinion. `reflect` also supports
`apply_all_directives=True`, meaning directives are a real concept in the
system, just not a parameter you set at bank-creation time (see
Corrections below).

**Other relevant features**: `retain` is idempotent via a `document_id`
field — re-running retain on the same content upserts rather than
duplicating; memories are scoped to isolated **banks** (`bank_id`), so
each consumer (a ticker, a symbol's research history, a whole portfolio)
can have its own bank rather than one undifferentiated pool; official
SDKs exist for Python/TypeScript/Go/Rust.

## One real caveat, not a marketing claim

A currently-open GitHub issue reports `reflect`/knowledge-page refresh
returning "I don't have information" on roughly half of calls despite the
data being present and retrievable, reproduced on versions 0.9.2 and
0.10.0 ([Issue #4378](https://github.com/vectorize-io/hindsight/issues/4378)).
Wherever `reflect`'s consolidated beliefs would inform a real decision —
capital sizing, timing, a research pivot — this reliability gap should be
verified against the current release before it's trusted in that role,
not assumed fixed because it's in the docs.

## Infrastructure cost of doing this

Self-hosting Hindsight requires Docker (or bare-metal via pip) plus
PostgreSQL with the pgvector extension (or Oracle AI Database 23ai) — a
real new service and a real new datastore, not just a pip install.
That's a legitimate infrastructure decision, not a trivial add — factor
it in before committing, separately from the "is this a good idea"
question for any specific consumer.

## Relationship to the maturity tier

Hindsight is a **retrieval tool**, not a source of truth and not a
computation engine — see `maturity-agentic-system-explanation.md` (same
folder) for the full architecture, but the short version: the database
stays the one source of truth, the deterministic `MaturityAssessor`
module reads it directly (not through Hindsight), and Hindsight only
ever retrieves — including the maturity tier itself, once retained, as
one more fact an agent can recall alongside everything else. Any
consumer that integrates Hindsight should gate its own confidence/
opinion-network beliefs the same maturity-tier-aware way: don't let
Hindsight's Opinion-network confidence outrun how much real evidence the
system has actually earned.

## Corrections to an earlier pasted integration proposal

A prior AI-generated summary of Hindsight (pasted into an earlier
conversation) got some details wrong, verified against the real client
source (`hindsight_client.py`):

- **`directives` is not a parameter of `acreate_bank`.** The real
  bank-creation parameters are `mission`,
  `disposition_skepticism`/`disposition_literalism`/`disposition_empathy`
  (or a `disposition` dict), `retain_mission`, `reflect_mission`,
  `background`, plus retrieval feature toggles. Directives are a real
  concept elsewhere (`areflect` has an `apply_all_directives: bool`
  parameter), just not set the way the earlier proposal showed.
- **`acreate_mental_model` was not confirmed** to exist in the client's
  public method list pulled from source. Mental models/knowledge pages
  are mentioned in Hindsight's docs as a real concept, but the exact SDK
  method for creating one wasn't verified — check the docs directly
  before writing code against it.
- Everything else in the earlier proposal (`bank_id`, `retain`/`recall`/
  `reflect` core shape, the four memory networks, disposition-as-
  skepticism/literalism/empathy) checked out against the real source.
