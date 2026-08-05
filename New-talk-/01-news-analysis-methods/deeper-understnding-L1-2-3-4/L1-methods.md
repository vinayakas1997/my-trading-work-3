---
name: L1-methods
status: discussion-phase
purpose: detail of Level 1 — news text only, no ML, no price. Everything that can be extracted from the words and timestamps alone. This is the pure-text layer and lives in vinu-news enrichment.
---

# L1 — News Text Only: Methods (No ML, No Price)

## What L1 is

Pure *description* of the news from its words alone. Output = features about what
the news is about. Nothing here says anything about the market.

## Method families

### 1. Keyword / rule methods

- Keyword matching and regex over headline + summary
- N-gram counting (which words/phrases co-occur)
- **Event-type classification by keyword groups**: e.g. split EARNINGS into
  EARNINGS_BEAT / EARNINGS_MISS / GUIDANCE_CUT / GUIDANCE_RAISE using keyword pairs
  ("beat"/"miss", "raised guidance"/"cut guidance")
- Extends this project's existing `category.py` keyword waterfall

### 2. Lexicon sentiment

- VADER (general-purpose rule-based sentiment)
- Loughran–McDonald finance sentiment dictionary
- FinBERT pretrained scoring (a model, but used as a frozen scorer — no training)
- All produce a single polarity/valence number

### 3. Text structure

- TF-IDF vectors (term frequency × inverse document frequency)
- Topic modeling: LDA, BERTopic
- Clustering: cosine similarity between headline vectors, greedy single-pass clustering

### 4. Entities & relations

- Named-entity extraction: countries, organizations, people, tickers
  (dictionary + regex, e.g. `"the fed" → Federal Reserve`, `\b[A-Z]{2,5}\b` for tickers)
- Structured event tuples: `(Actor, Action, Object, Time)` via SRL/dependency parsing
- Knowledge-graph enhancement of entities

### 5. Text quality / source

- Readability scoring
- Source reliability weighting
- Duplication / novelty detection (TF-IDF cosine similarity to prior coverage)
- Multi-source triangulation: same story on ≥3 independent sources → credibility signal

### 6. Temporal patterns in text alone

- News velocity / spike: articles per hour vs a rolling baseline (z-score anomaly detection)
- Repeated-event detection over a rolling window

## Candidates already catalogued in `../methods/`

All 8 candidate methods are L1 (or L1+L2):

| Method | Family | Needs price? |
|---|---|---|
| event-type-classification | keyword rules | No |
| named-entity-recognition | entities | No |
| velocity-spike-anomaly-detection | temporal | No |
| multi-source-triangulation | source/credibility | No |
| tfidf-semantic-clustering | text structure | No |
| vader-finance-tuned-sentiment | lexicon sentiment | No |
| llm-sentiment-classifier-alternatives | L2 (ML sentiment) | No |
| structured-event-tuple-embeddings | L2 (ML embeddings) | No |

## Output of L1

A feature set describing what each article is about: category/event-type labels,
entity tags, credibility flags, novelty scores, velocity flags, sentiment polarity.

## Requirements

- No ML training, no price data, no LLM calls (for the keyword/dictionary methods)
- Needs: text (headline + summary), timestamp, source name, ticker list

## What L1 feeds

L1 features are the input candidates for L2 (ML on text) and, after L3 validation,
the feature matrix for L4 prediction.
