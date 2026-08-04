---
name: tfidf-semantic-clustering
status: candidate-not-implemented
purpose: reference note on a TF-IDF headline-clustering method found in the fincept-terminal reference repo, for the 06-news-analysis-fix redesign discussion — not yet evaluated or built. Closely related to this project's existing novelty.py.
---

# TF-IDF Semantic Clustering — Grouping Same-Story Articles Without ML

## What is it

Groups articles that are "about the same thing" using TF-IDF cosine
similarity between headlines/summaries — a lightweight alternative to an
embedding model for detecting duplicate/near-duplicate coverage across
sources.

## How it works

1. Tokenize each article's headline+summary: lowercase, extract 3+
   letter words, strip stopwords, and **normalize synonyms/variants**
   to a canonical token first (`"fed"`/`"federal"`/`"reserve"` all map
   to `federal_reserve`; `"rates"`/`"rate"` → `interest_rate`;
   `"crashed"`/`"crashes"` → `crash`) — this synonym-folding step is
   what makes the bag-of-words clustering actually work well on financial
   headlines, where the same event gets phrased many different ways.
2. Build a manual TF-IDF matrix (no sklearn dependency in the reference
   implementation — hand-rolled `tf * idf` with `idf = log((N+1)/(df+1)) + 1`).
3. Pairwise cosine similarity between all article vectors.
4. Single-pass greedy clustering: for each unassigned article, group it
   with every other unassigned article whose cosine similarity is
   `>= 0.25`.
5. Return clusters sorted by size, largest first.

## Requirements

- **No LLM call** — pure TF-IDF, same class of method as this project's
  existing `novelty.py`.
- **Formula**: standard TF-IDF (`tf(w,d) * idf(w)`) + cosine similarity;
  threshold `0.25` is a tuned constant from the reference repo, not a
  principled derivation — would need re-tuning against this project's
  own headline style before trusting the exact threshold.
- Dependency: none beyond stdlib (`math`, `collections`) if reusing the
  reference implementation directly, since it deliberately avoids
  sklearn; `vinu-news`'s own `novelty.py` already depends on
  `sklearn.feature_extraction.text.TfidfVectorizer` /
  `sklearn.metrics.pairwise.cosine_similarity`, which is a strictly
  better-tested implementation of the same math — no reason to reimplement
  by hand here.

## Source

`personal-important/other-reference-repos/ref-fincept-terminal/fincept-qt/scripts/news_nlp.py`
— function `cluster_semantic()`.

## Notes for future reference

- **This overlaps heavily with `vinu-news`'s existing `novelty.py`** —
  same underlying technique (TF-IDF + cosine similarity), different use:
  `novelty.py` asks "is this article similar to anything *recent*"
  (backward-looking, per-article, time-windowed), this asks "which
  articles in this whole batch are similar to *each other*" (clustering,
  not a per-article backward comparison). **Don't build a second TF-IDF
  pipeline** — this is really a different *query* over the same
  vectorization `novelty.py` already does; the two should likely share a
  vectorizer/similarity function rather than being separate code paths.
- The **synonym-normalization dictionary** is the one genuinely new,
  worth-porting idea here — `novelty.py` doesn't currently fold synonyms
  before vectorizing, which likely weakens its similarity scores on
  headlines that describe the same event with different words (a real,
  fixable gap, cheap to test).
- Directly useful for **goal 2** (cascades) as a *better* thread-grouping
  mechanism than whatever currently assigns `thread_id` — worth checking
  what the existing thread-clustering logic actually is before assuming
  this needs to be new code vs. a threshold tune on existing code.
