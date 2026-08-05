---
name: financial-knowledge-graph-extraction
status: candidate-not-implemented
purpose: reference note on LLM-built financial knowledge graphs of entity relationships, found via web search Aug 2026 — the concrete 2026 realization of the knowledge-graph follow-up already flagged in structured-event-tuple-embeddings.md. Parked here (moved from 03-claude-new-methods) because it fails Final-implementation limitation #1 (no LLM implementation for now).
---

# Financial Knowledge Graph Construction from News

## Title / what it is

An LLM-based extraction module reads unstructured news and builds a
lightweight knowledge graph of entity *relationships* — which companies
compete with, supply, partner with, or litigate against which others —
rather than tagging each article with a single isolated event. Uses a
simplified schema focused on dynamic competitive/cooperative binary
relations, not a full general-purpose knowledge graph.

## Explanation — how it works

1. LLM extraction over news text identifies entities (companies, largely —
   overlaps with the existing NER work) and the relationship type between
   pairs of them mentioned together in an article.
2. These relations accumulate into a graph over time — edges can strengthen,
   weaken, or flip (competitor → partner) as new news arrives.
3. Downstream, a graph-aware model (e.g. an adaptive residual network in one
   cited paper) reasons over the graph structure alongside price, rather than
   over sentiment scores alone — and is reported to outperform sentiment-only
   forecasting.

## Input

A **stream/batch of news articles accumulating over time** — the graph
is built incrementally across many articles, not from a single article
in isolation (though each individual extraction step reads one article
at a time to propose relations to add to the graph).

## Output format

Not a score — an evolving **graph structure** (entity nodes,
relationship-typed edges with strength/direction), queried downstream
rather than read as a single value per article.

## Impact — what can be extracted

Second-order reasoning a per-article event tag can't represent: a supplier's
bad earnings implies something about its customers; a competitor's product
win implies something about its rival. This is structurally different from
every other L1/L2 method catalogued so far, which all reason about **one
article about one entity** — this reasons about the **network** of entities.

## Is it LLM-dependent?

Yes, for the relation-extraction step. The graph algorithms/embedding step
that consumes the resulting graph (once built) can be classical graph ML
(GNN, residual network over graph features) rather than LLM-dependent.

**This is why it's parked here**: Final-implementation limitation #1 rules
out any LLM-dependent method for now — revisit once that limitation lifts.

## Model size / base model (from source)

Ambiguous in FinKario: the paper's text references several financial LLMs
in its background/comparison discussion — FinBERT, BloombergGPT, FinGPT,
Qwen3 — but which of these (if any) is the model actually used for
FinKario's own knowledge-graph construction wasn't clearly extractable from
the PDF; the methodology section (where this would be stated) wasn't
legible in this extraction attempt. The Springer companion paper's page
requires an institutional login and couldn't be checked at all. Treat as
unresolved until the paper's methods section is read directly.

## Data sources needed

News text only for construction (an extension of the entity-extraction work
already catalogued in
`../../01-news-analysis-methods/pure-keyword-methods/named-entity-recognition.md`,
adding the relationship dimension on top of bare entity tags). Price needed
downstream for validating whether graph-structure changes precede price
moves.

## Fit with existing project structure

This is the concrete, named 2026 realization of the "knowledge-graph
enhancement" follow-up work already flagged (as a forward-looking note, not
a plan) in
`../../01-news-analysis-methods/pure-keyword-methods/structured-event-tuple-embeddings.md`
step 4. Also a natural heavier extension of
`named-entity-recognition.md`, which currently only extracts entities, not
relations between them.

## Source

- [FinKario: Event-Enhanced Automated Construction of Financial Knowledge Graph](https://arxiv.org/abs/2508.00961) — `arXiv:2508.00961`
- [Beyond sentiment: knowledge graph-driven financial market forecasting with large language models-extracted enterprise relations and adaptive residual networks](https://link.springer.com/article/10.1007/s41060-026-01064-2) — Springer, *International Journal of Data Science and Analytics*
