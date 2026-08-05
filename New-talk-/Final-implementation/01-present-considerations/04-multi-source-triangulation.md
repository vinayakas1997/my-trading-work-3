---
name: multi-source-triangulation
status: candidate-not-implemented
purpose: reference note on a story-credibility signal found in the fincept-terminal reference repo. Moved here from 01-news-analysis-methods/pure-keyword-methods/ — survives both Final-implementation limitations (no LLM, no pre-trained model — string comparison + set counting).
---

# Triangulation — Multi-Source Confirmation as a Credibility Signal

## What is it

A signal that flags when the *same story* is reported by 3 or more
independent sources, as a proxy for "this is a confirmed, real event,"
not a single outlet's rumor, speculation piece, or error.

## How it works

1. For each article, take a normalized key from its headline (the
   reference implementation just truncates to the first 50 characters —
   crude, works because near-duplicate headlines about the same story
   tend to share their opening).
2. Group articles by that key; collect the distinct `source` values per
   group.
3. If `len(distinct_sources) >= 3`, emit a `triangulation` signal with
   `severity: medium` and the list of confirming sources.

## Input

Not single-article — a **batch of articles**, grouped by normalized
headline key, so the same story from multiple sources can be compared
against each other. A single article alone can never trigger this signal.

## Output format

A boolean flag (`triangulation: true/false`), a fixed severity label
(`medium`), and the list of confirming source names — no numeric score,
just presence plus the evidence list.

## Requirements

- **No LLM call, no pre-trained model** — string comparison + set
  counting only.
- **Formula**: none beyond counting distinct sources per matched-headline
  group.
- Needs `source`/`provider` populated per article (already present in
  this project's `articles` table).
- **Caveat on the matching method**: first-50-characters string matching
  is fragile — two sources phrasing the same event's headline differently
  ("Apple beats Q3 estimates" vs "AAPL Q3 earnings top forecasts") would
  NOT match, undercounting real triangulation. `vinu-news` already has a
  better tool for this exact problem: `novelty.py`'s TF-IDF cosine
  similarity is a strictly better way to group "same story, different
  wording" than prefix matching — reuse that grouping logic instead of
  porting the crude version.

## Source

`personal-important/other-reference-repos/ref-fincept-terminal/fincept-qt/scripts/news_correlation.py`
— function `detect_signals()`, the `triangulation` signal block.

## Notes for future reference

- Directly useful as a **confidence multiplier** on top of any other
  signal (event-type classification, velocity spike, abnormal-return
  significance): a high-impact event confirmed by 5 sources is a
  different situation than the same event-type tag appearing in one
  low-quality feed.
- Cheap to compute relative to its value — worth prioritizing as an early
  addition once the story-grouping problem (see caveat above) is solved
  via the existing `novelty.py` machinery rather than reimplemented.
- Not by itself a *direction* or *magnitude* signal — combine, don't
  substitute.
