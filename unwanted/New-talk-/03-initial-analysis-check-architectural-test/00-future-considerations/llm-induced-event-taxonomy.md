---
name: llm-induced-event-taxonomy
status: candidate-not-implemented
purpose: reference note on constructing the event-type taxonomy itself via LLM induction rather than hand-curated keywords, found via web search Aug 2026 — an upgrade path for event-type-classification.md, not a competing method. Parked here (moved from 03-claude-new-methods) because it fails Final-implementation limitation #1 (no LLM implementation for now).
---

# LLM-Induced Hierarchical Event Taxonomy

## Title / what it is

A way to *build* the event-type taxonomy itself, instead of hand-writing one.
`event-type-classification.md` (in `../../01-news-analysis-methods/pure-keyword-methods/`)
proposes extending `category.py`'s keyword waterfall with finer sub-categories
(`EARNINGS_BEAT`/`EARNINGS_MISS`/etc.) chosen by a human. This method replaces
that human-authored step: an LLM reads batches of the actual news stream,
proposes candidate event-type categories, iteratively merges/splits them as
more data is seen, and a human does a final correction pass — producing a
taxonomy shaped by what's actually in this project's news data rather than a
guess made in advance.

## Explanation — how it works

1. Feed the LLM batches of article headlines/summaries (no price).
2. The LLM proposes an initial set of event-type categories.
3. On subsequent batches, the LLM either assigns articles to existing
   categories or proposes new ones / merges near-duplicate ones — an
   iterative induction loop, not a single pass.
4. A human reviews and corrects the evolving hierarchy periodically.
5. Once the taxonomy stabilizes, applying it to new articles could go back to
   being cheap (keyword rules or a lightweight classifier trained on the
   induced labels) — the LLM cost is concentrated in the taxonomy-construction
   phase, not per-article inference forever.

## Input

**Batches of articles**, fed iteratively to the LLM during the
taxonomy-construction phase (the induction loop needs to see many
articles to propose/merge categories). Once the taxonomy is stable,
applying it to classify a new article would be single-article, same as
`01-event-type-classification.md`.

## Output format

A categorical event-type label per article, drawn from the induced
taxonomy (13 groups, 57 specific types) — same shape as
`../01-present-considerations/01-event-type-classification.md`, just with
a richer, data-derived label set. During the construction phase itself,
the output is the taxonomy structure (the category tree), not a
per-article label.

## Impact — what can be extracted

A finer-grained, data-derived category tree instead of a fixed 8-bucket list
guessed upfront. Likely surfaces event types this project's current taxonomy
either misses entirely or over-merges into a generic bucket (e.g. `ECONOMIC`
lumping together very different sub-events). Feeds the same downstream slot
`event-type-classification.md` already targets: `significance_model.py`'s
categorical-feature slot, validated against `ar_significant`/`car_1h`.

## Is it LLM-dependent?

Yes, for the taxonomy-construction phase (the iterative induction loop
requires an LLM reading and proposing/merging categories across batches).
Once the taxonomy is stable, per-article classification could potentially
revert to a cheaper method (keyword rules or a small trained classifier) —
same cost-reduction path `event-type-classification.md` already notes for
LLM structured-output classification generally.

**This is why it's parked here**: Final-implementation limitation #1 rules
out any LLM-dependent method for now — revisit once that limitation lifts.

## Model size / base model (from source)

The paper names concrete models but does not itself state their parameter
counts:
- **Core LLM**: DeepSeek-V3 — used across the pipeline's LLM roles
  (extraction, merging, tracking, reasoning, retrieval, prediction — the
  paper uses functional names like `LLM_ext`/`LLM_merge` but doesn't
  indicate separate models per role).
- **Text embeddings**: BGE-M3 (`BAAI/bge-m3`).
- Publicly known sizes for these models (not stated in the paper itself —
  external knowledge, verify current figures before relying on them):
  DeepSeek-V3 is a ~671B-parameter Mixture-of-Experts model (~37B activated
  per token); BGE-M3 is a ~568M-parameter embedding model.

## Data sources needed

News text only (headline + summary). No price data needed for the
taxonomy-construction or classification step itself — price only enters later
at the L3 validation stage, same as every other L1/L2 method in this project.

## Fit with existing project structure

Directly upgrades
`../../01-news-analysis-methods/pure-keyword-methods/event-type-classification.md`
— specifically its "Option 2 (LLM structured-output classification)" path,
by replacing the fixed a-priori taxonomy with an induced one. Doesn't change
where the output lands downstream (still `significance_model.py`'s
categorical slot, still validated the same way).

## Source

Confirmed source (follow-up search pinned this down): the taxonomy-induction
methodology is part of the same StockMem paper documented in
`stockmem-event-reflection-memory.md` (same folder), not a separate paper —
it calls the method "LLM-driven Iterative Induction and Human Correction."
Per the paper: in each iteration the LLM processes news batches in two
steps — (1) judge whether an event fits an existing category, (2) propose
new categories for events that don't fit — converging on a taxonomy of 13
event groups refined into 57 specific event types for financial news
classification.

- [StockMem: An Event-Reflection Memory Framework for Stock Forecasting](https://arxiv.org/abs/2512.02720) — `arXiv:2512.02720`
