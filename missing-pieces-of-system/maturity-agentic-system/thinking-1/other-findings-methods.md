# Other memory-harness methods considered — a survey beyond Hindsight

## Context

This doc follows `six-agents-critique-and-hindsight-memory-resolution.md`
(same folder), which resolved the raw-memory-growth problem for
Hindsight specifically. Before locking Hindsight in as the *only*
memory harness for every bank, a live web search was run to check
whether a more mature or better-fitting method exists — particularly
for the portfolio/correlation bank, whose content (time-varying
relationships between tickers, regime-conditional truths) is
structurally different from a single ticker's own narrative. This is
that survey, and the reasoning behind the resulting hybrid
recommendation.

Sources are listed in full at the bottom; every claim below was
verified via live search, not recalled from training data.

---

## 1. Clearing up "Hermes"

"Hermes Atlas" (`hermesatlas.com`) is not a competing memory harness —
it's a directory/catalog site that lists and reviews memory providers,
including Hindsight itself. The actual "Hermes Agent" behind it (Nous
Research) is a full agent runtime with its own 7-layer memory system
(a persistent vector store on Qdrant, structured facts, "fabric
recall," an auto-curated wiki).

**The one design principle worth borrowing from it regardless of what
gets adopted here**: Hermes treats memory as a *pluggable provider
layer*, not a fixed choice — a base layer that always runs, plus 8
swappable backing architectures behind one interface. This is worth
carrying into this system's own design even without adopting Hermes
itself: the brain should talk to memory through a thin adapter, not be
wired directly to Hindsight's specific API everywhere it's used — so
the backing store (Hindsight, Graphiti, something else entirely) stays
swappable later without a rewrite.

## 2. The real finding: Zep/Graphiti for the portfolio/correlation bank

**What it is**: Graphiti (open-source, powers Zep's enterprise "Context
Lake") is a **bi-temporal knowledge graph** purpose-built for agent
memory — described in its own documentation as tuned for "millions of
small, mostly-cold graphs," which maps unusually well onto "many
per-ticker graphs" as a deployment shape.

**The structural difference from Hindsight**: every fact in Graphiti is
a graph edge carrying four timestamps — `valid_at`/`invalid_at` (when
it was true *in the world*) and `created_at`/`expired_at` (when the
system *learned* it). A superseded fact is explicitly **invalidated**,
not merely deprioritized at retrieval time the way Hindsight's
recency-weighting deprioritizes stale raw facts. The graph knows, as a
first-class fact: "this correlation held from March to July, then
broke" — not something inferred after the fact from an Observation's
freshness metadata.

**Why this matters for this system specifically**: the portfolio/
correlation bank (from Critique 4 in the previous doc — E's ticker-pair
correlation findings, plus the regime-conditional-truth problem named
all the way back in `../hindsight-memory-harness-explanation.md`,
"momentum tends to fail on AAPL in high-vol regimes") is *literally*
relational, time-varying data — a graph edge between two ticker nodes
whose weight and validity change over time, not a single entity's
prose narrative. That is exactly Graphiti's native shape, not
Hindsight's.

**Independent validation on the specific axis that matters most here**:
on LongMemEval (a benchmark specifically for temporal reasoning),
Graphiti scores 71.2% versus Mem0's 49% — a 22-point gap on exactly
"does this system correctly reason about *when* something was true,"
which is the same axis Mem0 was already rejected on once, in the
original Hindsight-selection doc.

**Where Hindsight still wins**: the per-ticker banks are single-entity
narratives (one ticker's forecasts, trades, provenance issues) more
than a web of relationships between entities. There's no clear case for
graph-model complexity there — Hindsight's simpler retain → consolidate
→ reflect pipeline, with tag-scoped Observations carrying `proof_count`
and freshness, is an adequate, simpler fit for that content.

## 3. A third option: reuse what's already built instead of adding new infra

Using an Obsidian vault (plain Markdown + `[[wikilink]]` backlinks,
queried via an MCP server) as agent memory is a real, current pattern —
several tools now index a vault for semantic search and graph
traversal, and multiple agents can share one vault as a common,
git-friendly fact base.

**Why this is more than a generic third option here**: this codebase
already has almost exactly the raw material for it, sitting unused —
the deterministic Markdown fact sheets
(`vinu_initial_analysis/storage/factsheet.py`, one file per
symbol+angle, regenerated every batch, cataloged in
`project-understanding/05-full-recorded-information/README.md` as item
53: "a readable projection... nothing reads the file back"). Extending
that into a proper cross-linked vault — tickers linking to shared
regime/angle notes, tagged the same way the Hindsight design already
tags retains — would give a human-and-agent-readable audit trail with
**zero new infrastructure**: no Postgres, no graph database, nothing to
self-host or babysit. It's not a substitute for the brain's actual
working memory, but it's a strong candidate for the "system self-report"
narrative layer discussed earlier, built entirely from an asset that
already exists and is currently dead weight.

## 4. The other frameworks considered, briefly, and why they weren't picked

- **Mem0** — already rejected once (documented in
  `../hindsight-memory-harness-explanation.md`) specifically for lacking
  a tiered retain-then-consolidate step; the LongMemEval gap found this
  pass (49% vs Graphiti's 71.2%) is independent confirmation that
  rejection was well-founded on the temporal-reasoning axis
  specifically, not just a general architecture preference.
- **Letta (formerly MemGPT)** — more an agent *runtime* than a memory
  add-on; adopting it would mean replacing this system's own already-
  developed agent orchestration (vinu-agent's teams, LLM roles), not
  adding a memory layer on top of it. Too large a change for what's
  needed here.

## 5. The resulting recommendation: a hybrid, deferred, not built yet

- **Portfolio/correlation bank** → Graphiti, when it's actually built —
  structurally the correct tool for time-varying relational facts.
- **Per-ticker banks** → Hindsight, as already designed in the previous
  doc — adequate fit, no reason to add graph complexity per single
  entity.
- **Human-facing audit trail** → extend the existing fact-sheet pattern
  into a linked vault, not a new product — reuses dead-weight
  infrastructure that already exists.
- **Access pattern, regardless of backend**: the brain should talk to
  memory through a thin, swappable adapter (per Hermes's own design
  principle), not be wired directly to any one provider's API.

**The catch, stated plainly**: self-hosted Graphiti needs its own graph
database (Neo4j or FalkorDB) — a *second* piece of self-hosted memory
infrastructure on top of Hindsight's own Postgres/pgvector requirement.
That's a real operational cost, not a free upgrade. Given this system's
own honest status — the LLM decision layer is still untested, there is
no live track record yet (per
`project-understanding/01-new-full-explanation-v2.md`'s "where things
honestly stand" section) — there isn't yet enough real correlation
history to justify standing up a second graph database for it today.

**This belongs in the design as the documented right answer for *when*
the portfolio bank becomes real** — not as something to build now,
ahead of Layer 0 and the single first analyst
(`agents-implementation-plan.md`'s Decision-Process analyst) that
remains the actual next concrete step.

## Sources

- [Best Memory Providers for Hermes Agent | Hermes Atlas](https://hermesatlas.com/lists/best-memory-providers)
- [The Hermes Agent Memory Guidebook | Hermes Atlas](https://hermesatlas.com/guide/memory/)
- [Best AI Agent Memory Frameworks in 2026: Compared and Ranked](https://atlan.com/know/best-ai-agent-memory-frameworks-2026/)
- [Best AI Agent Memory Systems in 2026: 8 Frameworks Compared](https://vectorize.io/articles/best-ai-agent-memory-systems)
- [AI Agent Memory 2026 — Comparing Mem0, Zep, Graphiti, Letta, LangMem | Medium](https://medium.com/@wasowski.jarek/i-compared-5-ai-agent-memory-systems-across-6-dimensions-none-wins-6a658335ed0a)
- [What Is a Temporal Knowledge Graph? | Zep](https://www.getzep.com/ai-agents/temporal-knowledge-graph/)
- [Graphiti: Temporal Knowledge Graphs for Agentic Apps - Zep](https://blog.getzep.com/graphiti-knowledge-graphs-for-agents/)
- [Graphiti: Knowledge graph memory for an agentic world - Neo4j](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [Give Your AI Agent Semantic Memory Over Your Obsidian Vault](https://omegamax.co/blog/omega-obsidian-vault-memory)
- [Vault Knowledge Base - Obsidian Plugin](https://community.obsidian.md/plugins/okb)

## Scope note

Like every doc in this folder, this is a survey and a recommendation,
not an implementation. Nothing here has been built or committed to.
