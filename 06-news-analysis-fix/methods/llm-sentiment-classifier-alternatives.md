---
name: llm-sentiment-classifier-alternatives
status: candidate-not-recommended
purpose: reference note on newer sentiment-classifier research (DeBERTa/RoBERTa/ensembles vs FinBERT) found via web search, for the 06-news-analysis-fix redesign discussion — documented for completeness, but flagged as unlikely to fix the actual problem this project already found.
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

## Requirements

- A different pretrained model (DeBERTa-based, or multiple models for an
  ensemble) in place of `ProsusAI/finbert` in
  `vinu-news/vinu_news/analysis/enrichment/finbert_sentiment.py`.
- Larger model than FinBERT in some configurations (DeBERTa-large exists;
  exact size used in the cited comparisons not confirmed) — likely higher
  CPU/inference cost than the current FinBERT setup, which is already the
  slowest-per-article of this project's three existing methods relative
  to its batch size.
- **No formula** — same softmax-classification output shape as FinBERT
  (positive/negative/neutral, or a continuous polarity score).

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
classification task (agreeing with human-labeled sentiment), which is a
different, already-solved-well-enough problem from predicting price
direction. There is no evidence in the cited papers, or anywhere in this
project's own testing, that a better sentiment classifier would flip the
already-disproven sentiment→direction relationship.

Documented here for completeness (the user asked what methods exist in
the research literature), but **not recommended as a next step** — the
structured event-representation direction
(`structured-event-tuple-embeddings.md`,
`event-type-classification.md`) targets the actual gap (what the event
*is*, structurally, not how positively/negatively it's worded), which the
existing disproven-signal finding doesn't rule out.
