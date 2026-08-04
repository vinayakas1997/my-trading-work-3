---
name: news-analysis-methods-index
status: discussion-phase
purpose: index of candidate methods for redesigning vinu-news's news-analysis pipeline, one file per method — sourced from the project's own reference repos (personal-important/other-reference-repos) and from web research. Nothing here is implemented; this is the discussion/evaluation phase before any code changes to 06-news-analysis-fix.
---

# News Analysis Methods — Candidate Index

## Why this folder exists

`04-advanced-aim-1`/`05-advanced-aim-1-1`'s work surfaced a real finding:
this project's three existing news-scoring methods
(`vinu-news/vinu_news/analysis/enrichment/sentiment.py`'s rule-based
lexicon, `finbert_sentiment.py`'s FinBERT, and
`analysis/llm/analyze.py`'s per-article LLM analysis) all reduce an
article to a single sentiment/valence number, and the seeded fact in
`vinu-agent/vinu_agent/facts/seed.py` already proved two of the three
(rule-based, FinBERT) don't predict price direction (~50% sign-agreement,
p>0.1) — a confirmed negative result, not an untested gap. The third
(LLM analysis) was found to have **zero downstream consumers** at all —
nothing reads its output.

Separately, `vinu-initial-analysis`'s `news_price_causality` angle
already has a genuinely rigorous event-study foundation (real Brown &
Warner market-model abnormal returns, a leak-safe XGBoost significance
classifier with honest per-run eval metrics, Granger causality, TF-IDF
novelty scoring) — the problem isn't the architecture, it's that the
*feature* being fed into all of it (sentiment score) has already been
shown to carry no directional signal.

This folder is the research/evaluation phase for what should replace or
complement that feature, before writing any code.

## The three original goals this is evaluating against

1. Find the news that actually drives price (event-timing attribution) —
   **already well-built**, see `impact.py`/`significance_model.py`.
2. Find cascaded news patterns (does a story's price impact escalate as
   coverage grows) — **half-built**: thread grouping exists
   (`aggregate_by_thread()`), but only as a post-hoc summary, not a
   real-time escalation signal.
3. Wording/pattern → probability of what happens next — **weakest link**:
   the only wording-based signal today is sentiment polarity, already
   proven not predictive of direction.

## Index

### Found in `personal-important/other-reference-repos/ref-fincept-terminal`

- [`velocity-spike-anomaly-detection.md`](velocity-spike-anomaly-detection.md)
  — news-volume anomaly detection (ratio + rolling z-score), no LLM
  needed. Targets goal 2.
- [`multi-source-triangulation.md`](multi-source-triangulation.md) — same
  story confirmed by 3+ sources, a credibility signal. No LLM needed.
- [`named-entity-recognition.md`](named-entity-recognition.md) — extract
  countries/orgs/people/tickers via dictionary+regex. No LLM needed.
  Feeds goal 3 and the structured-event methods below.
- [`tfidf-semantic-clustering.md`](tfidf-semantic-clustering.md) —
  headline clustering via TF-IDF cosine similarity; overlaps with this
  project's existing `novelty.py`, worth merging not duplicating.
- [`vader-finance-tuned-sentiment.md`](vader-finance-tuned-sentiment.md)
  — a third sentiment engine; flagged as unlikely to fix the actual
  disproven-signal problem, documented for completeness.

### Found via web search (research literature)

- [`structured-event-tuple-embeddings.md`](structured-event-tuple-embeddings.md)
  — **the most promising direction found**: represent "what happened"
  (Actor/Action/Object + learned embedding) instead of "how it feels"
  (sentiment). Directly targets why the existing methods failed. Real
  training pipeline required, not a zero-shot call.
- [`event-type-classification.md`](event-type-classification.md) — the
  cheap, low-effort subset of the above: a finer-grained categorical
  event-type tag (earnings beat vs. miss, etc.) instead of a full learned
  embedding. **Recommended as the first thing to actually test**, since
  it's cheap and reuses infrastructure (LLM calls, `significance_model.py`'s
  categorical-feature slot, `ar_significant` labels) that already exists.
- [`llm-sentiment-classifier-alternatives.md`](llm-sentiment-classifier-alternatives.md)
  — newer sentiment classifiers (DeBERTa, ensembles) reported to beat
  FinBERT on accuracy. **Not recommended** — a better sentiment
  classifier doesn't address the actual finding (sentiment ≠ direction,
  regardless of which model produces the sentiment score).

## What "done" looks like for this discussion phase

Not code — a decision on which 1-2 methods above are worth actually
testing against this project's own AAPL/TSLA/JNJ history (using the
already-existing `ar_significant`/`car_1h` labels from `impact.py` as
ground truth, the same discipline `significance_model.py` already uses),
before any of these get built into the real pipeline.

## What this folder does not cover

- Implementation — every file here is `status: candidate-not-implemented`
  (or `candidate-not-recommended`). Nothing has been built or tested yet.
- The existing, already-working event-study machinery
  (`news_price_causality/impact.py`, `_helpers.py`,
  `significance_model.py`, `granger.py`, `correlation.py`,
  `regime_features.py`) — that's documented in the code itself and
  doesn't need re-explaining here; this folder is specifically about what
  might *replace or add to* the sentiment-score feature it currently
  consumes.
