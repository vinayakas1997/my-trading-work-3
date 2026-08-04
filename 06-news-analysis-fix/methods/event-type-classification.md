---
name: event-type-classification
status: candidate-not-implemented
purpose: reference note on a simpler, lower-effort version of structured event representation — extending this project's existing category.py rather than building full event embeddings. For the 06-news-analysis-fix redesign discussion, not yet evaluated or built.
---

# Event-Type Classification — The Lower-Effort Version of Structured Events

## What is it

A finer-grained categorical tag for what *kind* of event an article
describes — not "EARNINGS" generically, but "earnings beat" vs. "earnings
miss" vs. "guidance cut" as distinct categories — used as a categorical
feature the same way this project's existing `category`/`priority`
fields already are, rather than a learned dense embedding (see
`structured-event-tuple-embeddings.md` for the full version this is a
cheaper subset of).

## How it works

Two possible implementations, in increasing order of effort:

1. **Keyword-rule extension** (matches this project's existing style):
   extend `vinu-news/vinu_news/analysis/enrichment/category.py`'s
   `CATEGORY_KEYWORDS` waterfall with finer sub-categories — e.g. split
   `EARNINGS` into `EARNINGS_BEAT`/`EARNINGS_MISS`/`GUIDANCE_CUT`/
   `GUIDANCE_RAISE` using keyword pairs (`"beat"`/`"miss"`,
   `"raised guidance"`/`"cut guidance"`). Same mechanism already in
   production, just a richer keyword table.
2. **LLM structured-output classification**: a single LLM call per
   article, prompted to pick from a fixed taxonomy of event types
   (earnings beat/miss, M&A announcement, regulatory action, analyst
   upgrade/downgrade, executive change, product launch, litigation,
   etc.) and return the label as JSON — same call shape as `vinu-news`'s
   existing `analyze_article()`, just a different, more specific
   question than "what's the sentiment."

## Requirements

- **Option 1 (keyword rules)**: no LLM call, no new dependency — purely
  extending an existing hand-written dictionary. Cheapest possible
  version; accuracy bounded by how well keyword pairs capture nuance
  (e.g. "beat lowered expectations" vs. "beat raised expectations" would
  likely both match "beat").
- **Option 2 (LLM classification)**: one LLM call per article, same cost
  class as the existing (already-found-to-be-unused)
  `analyze_article()` LLM call this project already pays for — could
  plausibly **replace** that call rather than add a new one, since
  nothing currently consumes its sentiment/summary output anyway (see
  `04-advanced-aim-1` conversation history: confirmed zero downstream
  consumers of `llm_analysis`).
- **Formula**: none — this is classification, not a computed score.
  Validation is a simple frequency/base-rate table: "of articles tagged
  `EARNINGS_MISS`, what fraction preceded a significant abnormal return,
  and in which direction" — directly reusable against the existing
  `impact.py`/`ar_significant` machinery already in
  `vinu-initial-analysis`.

## Source

Synthesized from this project's own existing code
(`vinu-news/vinu_news/analysis/enrichment/category.py`) plus the
structured-event-representation research direction found via web search
(see `structured-event-tuple-embeddings.md`'s sources) — not itself
found verbatim in a reference repo or paper; this is the "cheap version"
of that research idea, proposed for this project specifically.

## Notes for future reference

- **This is the recommended first step**, not the full embedding
  pipeline — it directly tests the actual hypothesis (does event *type*,
  as opposed to event *sentiment*, carry predictive signal) with a
  fraction of the effort, using infrastructure (LLM calls, the
  `significance_model.py` categorical-feature slot, the `ar_significant`
  event-study label) that already exists in this codebase today.
- If option 2 is chosen, **route it through the same
  `signal_contract.py` discipline** already used for
  `significance_score`/`regime_feature` — tag whatever this produces
  with `proven_for`/`not_proven_for` once tested, rather than letting it
  become a fourth untagged signal like the raw `sentiment_score` feeding
  `ml_model_pipeline` currently is.
- Directly testable against this project's own already-collected AAPL/
  TSLA/JNJ history without needing new data — the abnormal-return labels
  (`ar_significant`, `car_1h`, etc.) already exist per article from
  `impact.py`; this would just be a new categorical feature to test
  against labels that already exist, which is a fast, low-risk
  experiment relative to most of the other methods in this folder.
