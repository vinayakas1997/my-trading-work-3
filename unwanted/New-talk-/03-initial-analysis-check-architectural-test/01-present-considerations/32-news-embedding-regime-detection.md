---
name: news-embedding-regime-detection
status: candidate-not-implemented
purpose: reference note on detecting market regime shifts from the semantic geometry of news embeddings rather than from price statistics, found via web search Aug 2026 — a missing cell in the combination matrix. Moved here from 03-claude-new-methods/ — survives Final-implementation limitation #1 (embedding model, not a generative LLM call); no confirmed source paper, so limitation #2 can't be checked yet.
---

# News-Embedding-Driven Regime Detection

## Title / what it is

Instead of detecting market regimes from price/volatility statistics alone
(the existing `regime_analysis` angle, HMM-based methods being the field's
dominant approach per the search results), cluster the *semantic geometry*
of news embeddings (e.g. FinBERT-style dense vectors) over time, and use
shifts in the embedding-cluster structure itself as a regime/volatility-shift
signal — attempting to detect a regime change from what the news is *about*
before it fully shows up in price.

## Explanation — how it works

1. Embed news articles over a rolling window using a dense text encoder
   (FinBERT or similar — same embedding step already discussed in L2, dense
   vectors preserved rather than collapsed to a sentiment scalar).
2. Cluster the embeddings and track the cluster structure's geometry over
   time (which topics/narratives are dominant, how tightly or loosely they
   cluster).
3. A shift in that geometry — new cluster emerging, existing clusters
   splitting/merging, overall dispersion changing — is treated as a
   candidate leading indicator of a volatility/regime shift, to be validated
   against actual subsequent price behavior.

## Input

A **rolling window of news articles (embedded) over time** — not a
single article; the method specifically tracks how the cluster geometry
of many articles' embeddings shifts across a time window.

## Output format

Not a numeric score — a regime-shift flag/label (e.g. "regime change
detected" at a given point in time) derived from a discrete change in the
embedding-cluster geometry, plus optionally which new regime/cluster the
news has moved toward.

## Impact — what can be extracted

This fills a cell the combination matrix
(`../../00-project-understanding/01-differnt-combination-analysis.md`)
doesn't currently have at all: the matrix has **price + regime** (existing
`regime_analysis`, price-derived) and **price + news** (existing
`news_price_causality`, news predicting *returns*), but not **news →
regime** as its own direction — using news content specifically to detect
regime *state*, not to predict price direction. If validated, it would give
`regime_analysis` an earlier-warning input than price-derived detection
alone, the same "detect it before price fully shows it" logic already
motivating `03-velocity-spike-anomaly-detection.md`.

## Is it LLM-dependent?

Partially. Producing the embeddings needs a text-embedding model (FinBERT or
similar — not an LLM generation call, closer to the existing L2 dense-vector
methods already documented). The clustering and regime-shift detection
itself is classical (unsupervised clustering + statistical shift detection),
not LLM-dependent at all. **This is why it survives limitation #1** — but
without a confirmed source paper, limitation #2 (2-3GB) can't be checked
against a specific model yet; a generic FinBERT-class embedding model
would comfortably fit.

## Model size / base model (from source)

Not applicable — no confirmed source paper exists for this method (see the
attribution caveat below), so there's no size to extract. If a real source
paper is found later, add its embedding-model size here.

## Data sources needed

News text (embedded) for the detection signal itself. Price is needed only
for validation — checking whether detected embedding-geometry shifts
actually preceded real regime/volatility changes, same L3-style discipline
used everywhere else in this project.

## Fit with existing project structure

Proposed new row for the combination matrix; would extend the existing
`regime_analysis` angle with a news-derived leading input rather than
replacing its price-based detection.

## Source

**Attribution caveat, unresolved even after a follow-up search**: the
original description ("detecting financial market regimes using semantic
geometry of news embeddings with clustering to predict volatility and regime
shifts ahead of price action") did not resolve to one specific citable
paper — it appears to be a search-engine summary blending several papers'
findings rather than describing one paper's method. Treat the method
description itself as a plausible research direction, not a verified,
already-published technique.

Closest related paper found (similar spirit — regime-conditioned fusion of
text-derived sentiment with price — but not the same mechanism; it
conditions fusion *on* a price-derived regime rather than *detecting* the
regime from news embeddings):

- [Bitcoin Price Direction Prediction via Regime-Aware Multi-Modal Fusion of Social Sentiment and Technical Features](https://arxiv.org/abs/2607.23370) — `arXiv:2607.23370` (RAML framework — regime state
  computed from rolling volatility, not from news-embedding clustering;
  cited here as the nearest adjacent work, not as direct support for this
  method as described)

Before pursuing this method, do a dedicated search for "news embedding
clustering regime detection" style papers rather than relying on this note
as pre-validated.
