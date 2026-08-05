---
name: stockmem-event-reflection-memory
status: candidate-out-of-scope
purpose: reference note on an agent-memory architecture for stock forecasting, found via web search Aug 2026 — already out of scope as agent-layer work (step 5, not vinu-initial-analysis), and doubly parked here (moved from 03-claude-new-methods) since it also fails Final-implementation limitation #1 (no LLM implementation for now).
---

# StockMem — Event-Reflection Memory Framework

## Title / what it is

Not an analysis angle — an **agent-memory architecture** for how a
forecasting agent remembers and reasons over past events across time. Two
memory layers: (1) **Event Memory**, which tracks how a market event evolves
via horizontal consolidation (across sources, at a point in time) and
longitudinal tracking (the same event/story over time), extracting
"expectation-discrepancy" signals — was the outcome a surprise relative to
what was already priced in, not just what direction it moved; (2)
**Reflection Memory**, which abstracts causal lessons from past
event→price-outcome pairs, so the agent can recall "last time this type of
event happened, this is what followed" rather than treating every event as
new.

## Explanation — how it works

1. Event Memory ingests news events over time, consolidates duplicate/
   related coverage of the same story, and tracks the story's evolution —
   producing an expectation-discrepancy signal (surprise vs. expected)
   rather than a raw sentiment or event-type tag.
2. Reflection Memory stores (event, subsequent outcome) pairs as
   experience, and abstracts a causal generalization from them, retrievable
   when a similar event recurs.
3. A noted open problem: **drift handling** — as market regimes shift (e.g.
   low → high volatility), old episodes with high surface-feature similarity
   may yield misleading expectations if reflected on naively.

## Input

A **stream of news events over time** (for Event Memory) plus a
**historical corpus of (event, price-outcome) pairs** (for Reflection
Memory) — both are batch/historical inputs, not single-article.

## Output format

Not a single score — Event Memory outputs an expectation-discrepancy
signal (was this a surprise, and in which direction, relative to what was
priced in); Reflection Memory outputs retrieved causal analogies/lessons
(text or structured recall) from similar past events. Both feed an
agent's reasoning, not a downstream ML feature column.

## Impact — what can be extracted

This is a *design pattern for the agent's memory*, not a feature-generation
method that outputs a column to feed `ml_model_pipeline` or
`significance_model.py`. It would inform how `vinu-research`/`vinu-agent`
recall and reason over prior pre-analysis runs, if and when that layer gets
designed.

## Is it LLM-dependent?

Yes, heavily — this is fundamentally an LLM-agent memory architecture (both
memory layers are built and queried via LLM reasoning over stored
event/outcome text).

**This is why it's parked here (doubly)**: it was already flagged
`candidate-out-of-scope` for being agent-layer work (step 5), and it also
fails Final-implementation limitation #1 (no LLM implementation for now) —
two independent reasons it's not near-term work.

## Model size / base model (from source)

Same models as `llm-induced-event-taxonomy.md` (same paper, same folder):
core LLM is **DeepSeek-V3** (used across all pipeline roles — extraction,
merging, tracking, reasoning, retrieval, prediction), text vectorization
uses **BGE-M3**. The paper doesn't state parameter counts itself; both are
publicly known models (DeepSeek-V3 ≈ 671B total / ~37B activated MoE,
BGE-M3 ≈ 568M) — external knowledge, verify current figures before citing
further.

## Data sources needed

News events + price outcomes (the Reflection Memory layer specifically
pairs the two into experience records).

## Fit with existing project structure — why this is out of scope right now

This belongs conceptually to **step 5** (the agentic-analysis framework:
vinu-research/vinu-simulator/vinu-agent) in the stage-1 build sequence
(`../../00-project-understanding/03-stage1-planning.md`), which is explicitly
**not** part of the current focus — the stated scope is steps 1–4, through
`vinu-initial-analysis`, with step 5 deliberately deferred until the
analysis layer is stable. Documented here so the idea isn't lost by the time
step 5 becomes relevant, not proposed as near-term work.

## Source

- [StockMem: An Event-Reflection Memory Framework for Stock Forecasting](https://arxiv.org/abs/2512.02720) — `arXiv:2512.02720` — note: this same
  paper is also the source for `llm-induced-event-taxonomy.md`'s (same
  folder) taxonomy-construction method (the "Event Memory" layer's taxonomy
  is built using that induction method).
