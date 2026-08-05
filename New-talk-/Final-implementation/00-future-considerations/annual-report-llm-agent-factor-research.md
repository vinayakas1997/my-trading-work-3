---
name: annual-report-llm-agent-factor-research
status: candidate-out-of-scope
purpose: reference note on CrossAlpha, an LLM-agent framework deriving cross-market factors from annual reports, found via web search Aug 2026 — already out of scope as agent-layer/heavy-data-source work, and doubly parked here (moved from 03-claude-new-methods) since it also fails Final-implementation limitation #1 (no LLM implementation for now).
---

# LLM-Agent Factor Research from Annual Reports (CrossAlpha)

## Title / what it is

A benchmark/framework (CrossAlpha) using LLM agents to read annual reports
(10-K-style filings) across multiple markets and derive cross-market
factors for factor research — i.e., LLM agents doing the "read the
fundamentals, propose a candidate factor" work a quant researcher would
otherwise do by hand, rather than extracting a single discrete event.

## Explanation — how it works

1. LLM agents ingest full annual reports across companies/markets.
2. Agents reason over the report content to propose candidate factors
   (fundamentals-derived signals expected to relate to returns).
3. Factors get benchmarked cross-market, per the framework's stated purpose
   as a benchmark for this kind of research.

## Input

A single full annual report at a time per company/year for reading, but
the factor-research process compares **across multiple companies and
markets** to derive cross-market factors — so the effective unit of
analysis is a set of annual reports, not one in isolation.

## Output format

Candidate factor definitions/exposures (structured, human-readable factor
proposals) rather than a numeric score per company — the "prediction" is
which factors to test, not a value.

## Impact — what can be extracted

Different in kind from the SEC 8-K method
(`sec-8k-filing-event-extraction.md`, same folder) — that one extracts
discrete, short-form *events* from filings due within 4 business days of a
trigger. This one derives longer-horizon *factors* from full annual reports,
which are long, low-frequency documents (typically one per company per
year). More a research-process pattern (agent proposes and tests a factor)
than a per-article feature that would feed `significance_model.py` or
`ml_model_pipeline` the way L1/L2 news features do.

## Is it LLM-dependent?

Yes, heavily — LLM agents reading and reasoning over long documents to
propose factors, not a fixed extraction schema applied uniformly.

**This is why it's parked here (doubly)**: it was already flagged
`candidate-out-of-scope` for being agent-layer/heavy-data-source work, and
it also fails Final-implementation limitation #1 (no LLM implementation for
now) — two independent reasons it's not near-term work.

## Model size / base model (from source)

Explicitly stated: **GPT-4o** is the LLM agent used to extract factor
exposures from annual reports. The paper (arXiv v3, 2026) also references
**GPT-5** in its model-documentation links, suggesting later
experiments/comparisons may include it, though the primary named extraction
agent is GPT-4o. Embeddings use **OpenAI's `text-embedding-3-small`**. No
parameter counts are given for either GPT-4o or GPT-5 — OpenAI doesn't
publish these.

## Data sources needed

Annual reports (a new, low-frequency data source) + price/factor data for
cross-market validation.

## Fit with existing project structure — why this is flagged out-of-scope

Two independent reasons this sits outside the current focus (steps 1–4,
through `vinu-initial-analysis`), on top of the LLM limitation:

1. It's simultaneously a **new data source** (fills part of the "price +
   fundamentals" cell in the combination matrix, like the 8-K method) *and*
   a **research-agent pattern** (agent proposes/tests factors) — the latter
   half belongs to step 5 (`vinu-research`), which is explicitly deferred.
2. Annual reports are a much lower-frequency, heavier data source than
   anything currently in vinu-news's scope (headlines/summaries) — even the
   pure data-ingestion half of this is a bigger lift than the 8-K filing
   method, which at least parallels the existing per-article extraction
   pattern.

Documented for completeness given it directly answers "price + fundamentals"
gap, but not proposed as near-term work.

## Source

- [CrossAlpha: An Annual-Report Benchmark for Cross-Market Factor Research](https://arxiv.org/abs/2605.29286) — `arXiv:2605.29286`
