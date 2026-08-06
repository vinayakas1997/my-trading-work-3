---
name: llm-sentiment-classifier-alternatives
status: candidate-not-recommended
purpose: reference note on newer sentiment-classifier research (DeBERTa/RoBERTa/ensembles vs FinBERT). Moved here from 01-news-analysis-methods/pure-keyword-methods/ — despite the "llm" in the filename, this survives Final-implementation limitation #1 (DeBERTa/RoBERTa are frozen classifier models, not generative LLM calls, same category as FinBERT); already flagged not-recommended for a separate, unrelated reason (see below). Check limitation #2 (2-3GB) against the specific DeBERTa variant before using.
---

# Newer Sentiment Classifiers (DeBERTa, RoBERTa, Ensembles) vs. FinBERT

## What is it

Recent (2025-2026) research comparing large-language-model-based sentiment
classifiers against FinBERT for financial news, reporting DeBERTa
outperforming FinBERT and RoBERTa on sentiment-classification accuracy
(~75%), with ensemble approaches (combining multiple classifiers' votes)
reaching ~80%.

## How it works

Same task shape as FinBERT — 3-way (or continuous) sentiment
classification of financial text — just a different/newer underlying
transformer model (DeBERTa's disentangled attention mechanism, or a
voting ensemble across several classifiers) claimed to classify sentiment
more accurately than FinBERT's BERT-base architecture.

## Input

A single article's text at a time — same per-article unit as FinBERT.

## Output format

Same shape as FinBERT — either a 3-way categorical label
(`positive`/`negative`/`neutral`) or a continuous polarity score,
depending on configuration. No new output shape versus what this project
already has.

## Requirements

- A different pretrained model (DeBERTa-based, or multiple models for an
  ensemble) in place of `ProsusAI/finbert` in
  `vinu-news/vinu_news/analysis/enrichment/finbert_sentiment.py`.
- Larger model than FinBERT in some configurations (DeBERTa-large exists;
  exact size used in the cited comparisons not confirmed) — check this
  against Final-implementation limitation #2 (2-3GB footprint) before
  picking a variant; DeBERTa-base (~140M params, ~0.3GB fp16) would fit
  comfortably, DeBERTa-large (~400M params, ~0.8GB fp16) would also fit,
  but the exact variant used in the cited papers wasn't confirmed.
- **No formula** — same softmax-classification output shape as FinBERT.

## Source

Found via web search, not a local reference repo:
- "Enhancing Trading Performance Through Sentiment Analysis with LLMs"
  https://arxiv.org/html/2507.09739v1
- "Impact of LLMs news Sentiment Analysis on Stock Price Movement
  Prediction" https://arxiv.org/html/2602.00086v1

## Notes for future reference — why this is flagged `not-recommended`

**This does not address the problem this project already proved out.**
The seeded fact in `vinu-agent/vinu_agent/facts/seed.py` tested two
different sentiment-scoring *methods* (rule-based lexicon, then FinBERT)
against real AAPL/TSLA/JNJ price data and found neither predicts
direction (~50% sign-agreement, p>0.1) — a negative result about the
*sentiment → direction* relationship itself, not about which specific
classifier does the sentiment scoring. A more accurate sentiment
classifier (DeBERTa vs. FinBERT) improves accuracy at the sentiment-
classification task, which is a different, already-solved-well-enough
problem from predicting price direction.

Documented here for completeness, but **not recommended as a next step**
— the structured event-representation direction
(`08-structured-event-tuple-embeddings.md`, `01-event-type-classification.md`)
targets the actual gap (what the event *is*, structurally), which the
existing disproven-signal finding doesn't rule out.

Note this is a **different reason for caution** than the two
Final-implementation limitations — this method technically survives both
(non-LLM classifier, plausibly under the size cap), but is separately
not recommended because it doesn't address the actual known problem.
