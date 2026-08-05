---
name: sec-8k-filing-event-extraction
status: candidate-not-implemented
purpose: reference note on structured event extraction from SEC 8-K regulatory filings, found via web search Aug 2026 — a new data source not currently ingested anywhere in this project, filling part of the "price + fundamentals" combination cell. Parked here (moved from 03-claude-new-methods) because it fails Final-implementation limitation #1 (no LLM implementation for now).
---

# SEC 8-K Filing Structured Event Extraction

## Title / what it is

The same "structured event extraction" idea already documented for news
headlines (`structured-event-tuple-embeddings.md`,
`event-type-classification.md`), applied instead to SEC Form 8-K filings —
using a fine-grained taxonomy of filing event types (executive changes,
material agreements, bankruptcy, asset sales, etc.) rather than treating an
8-K as one undifferentiated "a filing happened" fact.

## Explanation — how it works

1. Ingest 8-K filings from SEC EDGAR for the tracked tickers.
2. Extract structured events using a fine-grained taxonomy (the source paper
   defines a taxonomy specifically for this) — an LLM structured-output call
   is the modern equivalent of the original extraction pipeline, same call
   shape as this project's existing `analyze_article()`.
3. Each filing yields one or more typed events with a timestamp (the filing
   date, which is itself meaningful — 8-Ks are legally required within 4
   business days of the triggering event).

## Input

A single SEC 8-K filing at a time — per-filing extraction, same unit as
per-article extraction for news.

## Output format

One or more structured typed events per filing, each with an event-type
label and the filing timestamp — e.g.
`{event_type: "executive_change", filing_date: ...}`, analogous to
`../01-present-considerations/01-event-type-classification.md` but for
filings instead of news.

## Impact — what can be extracted

A structurally different signal from news: filings are *legally mandated*
disclosures with a hard deadline, so they carry higher reliability and less
noise than press coverage, which can be rumor-based, delayed, or
speculative. Could serve two roles: (a) a standalone event feed with its own
L3-style validation against price, or (b) a **triangulation/confidence
signal** on top of news-derived event tags — a news story about an executive
departure corroborated by the actual 8-K filing is a different confidence
level than the news story alone (same spirit as
`multi-source-triangulation.md`, but filing-vs-news instead of source-vs-source).

## Is it LLM-dependent?

Yes, for the extraction step — a structured-output LLM call per filing,
analogous to the existing `analyze_article()` pattern already used for news.

**This is why it's parked here**: Final-implementation limitation #1 rules
out any LLM-dependent method for now — revisit once that limitation lifts.

## Model size / base model (from source)

The paper deliberately does not name the extraction model: "a compact,
commercially available instruction-tuned model at temperature zero" — the
authors' stated design goal is that "reliability comes from the surrounding
structure rather than from model scale," so no size is disclosed. The
**judge/grading model is named explicitly: Opus 4.8** (a Claude model),
described as "a more capable model than the extraction model" — used only
for evaluating extraction quality, not for extraction itself.

## Data sources needed

**Filings text** — a genuinely new data source, not currently part of
vinu-news's ingestion at all (would need a new SEC EDGAR ingestion path).
No price needed for extraction itself; price is needed afterward for
L3-style validation (does a given 8-K event type precede a significant
abnormal return, same discipline as `impact.py`).

## Fit with existing project structure

Fills part of the **"price + fundamentals"** row in the combination matrix
(`../../00-project-understanding/01-differnt-combination-analysis.md`), which
currently reads "no" for this project. Requires new ingestion infrastructure
— this is a bigger lift than any L1/L2 news method, which all operate on
data vinu-news already has.

## Source

- [Grounded Event Extraction from SEC 8-K Filings with a Fine-Grained Taxonomy](https://arxiv.org/abs/2607.08346) — `arXiv:2607.08346`
