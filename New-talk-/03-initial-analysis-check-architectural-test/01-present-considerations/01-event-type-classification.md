---
name: event-type-classification
status: candidate-not-implemented
purpose: reference note on a simpler, lower-effort version of structured event representation — extending this project's existing category.py rather than building full event embeddings. Moved here from 01-news-analysis-methods/pure-keyword-methods/ — survives both Final-implementation limitations via Option 1 (keyword-rule path, no LLM, no pre-trained model).
---

# Event-Type Classification — The Lower-Effort Version of Structured Events

## What is it

A finer-grained categorical tag for what *kind* of event an article
describes — not "EARNINGS" generically, but "earnings beat" vs. "earnings
miss" vs. "guidance cut" as distinct categories — used as a categorical
feature the same way this project's existing `category`/`priority`
fields already are, rather than a learned dense embedding (see
`08-structured-event-tuple-embeddings.md` for the full version this is a
cheaper subset of).

## How it works

Two possible implementations, in increasing order of effort:

1. **Keyword-rule extension** (matches this project's existing style, and
   the only path that survives the Final-implementation limitations):
   extend `vinu-news/vinu_news/analysis/enrichment/category.py`'s
   `CATEGORY_KEYWORDS` waterfall with finer sub-categories — e.g. split
   `EARNINGS` into `EARNINGS_BEAT`/`EARNINGS_MISS`/`GUIDANCE_CUT`/
   `GUIDANCE_RAISE` using keyword pairs (`"beat"`/`"miss"`,
   `"raised guidance"`/`"cut guidance"`). Same mechanism already in
   production, just a richer keyword table.
2. **LLM structured-output classification** (ruled out for now —
   `../limitations_and_other_info.md` limitation #1): a single LLM call per
   article, prompted to pick from a fixed taxonomy of event types
   (earnings beat/miss, M&A announcement, regulatory action, analyst
   upgrade/downgrade, executive change, product launch, litigation,
   etc.) and return the label as JSON.

## Input

A single article (headline + summary) at a time — same per-article unit
`category.py` already uses today. Not a batch or window.

## Output format

A single categorical label per article (e.g. `EARNINGS_BEAT`,
`EARNINGS_MISS`, `GUIDANCE_CUT`, `GUIDANCE_RAISE`) — a string tag, not a
numeric score, stored the same way `category`/`priority` already are today.

## Requirements

- **Option 1 (keyword rules)**: no LLM call, no new dependency — purely
  extending an existing hand-written dictionary. Cheapest possible
  version; accuracy bounded by how well keyword pairs capture nuance
  (e.g. "beat lowered expectations" vs. "beat raised expectations" would
  likely both match "beat").
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
(see `08-structured-event-tuple-embeddings.md`'s sources) — not itself
found verbatim in a reference repo or paper; this is the "cheap version"
of that research idea, proposed for this project specifically.

## Notes for future reference

- **This is the recommended first step**, not the full embedding
  pipeline — it directly tests the actual hypothesis (does event *type*,
  as opposed to event *sentiment*, carry predictive signal) with a
  fraction of the effort, using infrastructure (the
  `significance_model.py` categorical-feature slot, the `ar_significant`
  event-study label) that already exists in this codebase today.
- Directly testable against this project's own already-collected AAPL/
  TSLA/JNJ history without needing new data — the abnormal-return labels
  (`ar_significant`, `car_1h`, etc.) already exist per article from
  `impact.py`; this would just be a new categorical feature to test
  against labels that already exist, which is a fast, low-risk
  experiment relative to most of the other methods in this folder.
