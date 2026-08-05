---
name: claude-new-methods-index
status: resolved
purpose: index of methods found via web search (Aug 2026) that were not covered in 01-news-analysis-methods or 02-price-analysis-methods. All 10 have now been triaged by Final-implementation's limitations and moved out — this folder is kept as a historical record of the search, not an active working folder anymore.
---

# Claude New Methods — Index (Resolved)

## Why this folder exists (historical)

A follow-up web search after the L1–L4 news framework and Kronos-family price
research was already documented, specifically asking: what modern method or
combination is missing? This folder held the 10 things that came back, one
file per method.

## Where everything went

All 10 were triaged against
`../Final-implementation/limitations_and_other_info.md` and moved out — this
folder no longer holds any method files itself, just this index.

**Moved to `../Final-implementation/01-present-considerations/`** (survive
both limitations):
- `cross-attention-gcn-news-price-fusion.md` → `29-cross-attention-gcn-news-price-fusion.md`
- `fincast-foundation-model.md` → `30-fincast-foundation-model.md`
- `finmamba-graph-state-space.md` → `31-finmamba-graph-state-space.md`
- `news-embedding-regime-detection.md` → `32-news-embedding-regime-detection.md`

**Moved to `../Final-implementation/00-future-considerations/`** (excluded —
LLM-dependent):
- `llm-induced-event-taxonomy.md`
- `sec-8k-filing-event-extraction.md`
- `earnings-call-transcript-signal.md`
- `financial-knowledge-graph-extraction.md`
- `stockmem-event-reflection-memory.md`
- `annual-report-llm-agent-factor-research.md`

## Related files

- `../Final-implementation/limitations_and_other_info.md` — the constraints
  that triaged everything out of this folder
- `../Final-implementation/01-present-considerations/00-index.md` — where the
  4 survivors now live, alongside 28 other methods from `01-news-analysis-methods`
  and `02-price-analysis-methods`
- `../Final-implementation/00-future-considerations/00-index.md` — where the
  6 excluded methods now live
- `../01-news-analysis-methods/` — the news-side research this folder extended
- `../02-price-analysis-methods/` — the price-side research this folder extended
