---
name: future-considerations-index
status: discussion-phase
purpose: index of the 7 methods excluded from Final-implementation by 00-limitation.md's limitation #1 (no LLM implementation for now). Parked here, not discarded — revisit once that limitation lifts.
---

# Future Considerations — LLM-Dependent Methods (Parked)

## Why this folder exists

`../00-limitation.md` sets two hard constraints for the Final-implementation
phase. Limitation #1 (no LLM implementation for now) rules out every method
below. Rather than deleting this research, each excluded method's full
writeup lives here — same one-file-per-method format used everywhere else in
`New-talk-` (title, explanation, impact, LLM-dependency, model size, data
sources, source links).

## The 7

Six moved from `../../03-claude-new-methods/` (that folder now only holds
the methods that survive both limitations), one written fresh here because
it previously only existed as an unsourced 4-line bullet in
`../../02-price-analysis-methods/price-analysis-methods.md`:

1. [`llm-induced-event-taxonomy.md`](llm-induced-event-taxonomy.md) — LLM
   induces the news event-type taxonomy from data instead of hand-curated
   keywords (StockMem paper's taxonomy method).
2. [`sec-8k-filing-event-extraction.md`](sec-8k-filing-event-extraction.md)
   — structured event extraction from SEC 8-K filings.
3. [`earnings-call-transcript-signal.md`](earnings-call-transcript-signal.md)
   — LLM-extracted trading signal from earnings-call transcripts.
4. [`financial-knowledge-graph-extraction.md`](financial-knowledge-graph-extraction.md)
   — LLM-built knowledge graph of entity relationships from news (FinKario).
5. [`stockmem-event-reflection-memory.md`](stockmem-event-reflection-memory.md)
   — agent-memory architecture (Event Memory + Reflection Memory). Doubly
   parked: already out-of-scope as agent-layer (step 5) work, and now also
   fails the LLM limitation.
6. [`annual-report-llm-agent-factor-research.md`](annual-report-llm-agent-factor-research.md)
   (CrossAlpha) — LLM agents deriving factors from annual reports. Doubly
   parked, same reasons as #5.
7. [`hybrid-llm-price-fusion.md`](hybrid-llm-price-fusion.md) — LLM-generated
   directional-sentiment + confidence signal, gated-fused with price in a
   Transformer (5.28% RMSE reduction vs. vanilla baseline). Newly written up
   in full here — never lived in `03-claude-new-methods` since it originated
   from `02-price-analysis-methods.md`, not the web-search follow-up.

## What "revisit" means

If limitation #1 ever lifts, come back here first — every file already has
its explanation, impact, and sources intact, so re-evaluating just means
re-running the size/deployment check (limitation #2) and the usual
`ar_significant`/`car_1h` validation discipline, not re-researching from
scratch.

## Related files

- `../00-limitation.md` — the constraints that put these methods here
- `../../03-claude-new-methods/00-index.md` — the sibling folder these 6 were
  moved out of; it now holds only the non-LLM survivors
- `../../02-price-analysis-methods/price-analysis-methods.md` — source of
  `hybrid-llm-price-fusion.md`'s original 4-line bullet
