---
name: multi-source-triangulation
status: candidate-not-implemented
purpose: reference note on a story-credibility signal found in the fincept-terminal reference repo, for the 06-news-analysis-fix redesign discussion — not yet evaluated or built.
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

## Requirements

- **No LLM call** — string comparison + set counting only.
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
  low-quality feed. Nothing in the current `vinu-news`/
  `vinu-initial-analysis` pipeline currently distinguishes single-source
  from multi-source stories at all.
- Cheap to compute relative to its value — worth prioritizing as an early
  addition once the story-grouping problem (see caveat above) is solved
  via the existing `novelty.py` machinery rather than reimplemented.
- Not by itself a *direction* or *magnitude* signal — it answers "how
  sure are we this happened," which is a different axis from "what does
  it mean" (event type) or "how big a deal is it" (velocity/significance
  score). Combine, don't substitute.
