---
name: 00-explanation-l1234
status: discussion-phase
purpose: the four-level framework for news-driven stock analysis — from pure text (L1) up to full text+price+ML prediction (L4). This is the general research taxonomy that the deeper-understnding-L1-2-3-4 folder is organized around; each level gets its own detailed file.
---

# Levels L1–L4 — The Four-Stage Framework for News-Driven Analysis

## The core idea

News text alone is just words. To get from words to trading signals you climb
four levels, each adding more information and more machinery:

```
L1  news text only                       → features describing what the news is about
L2  news text + ML models                → richer learned features (ML applied to text)
L3  news text + stock price (statistics) → evidence: which news types actually move price
L4  news text + stock price + ML         → a predictive model, honestly evaluated
```

## Level 1 — News text only (no ML, no price)

What you can extract from the words themselves. Pure *description* of the news.

- Keyword/regex methods, n-gram counting, event-type classification by keyword groups
- Lexicon sentiment (VADER, Loughran–McDonald), FinBERT pretrained scoring
- Text structure: TF-IDF vectors, topic modeling (LDA/BERTopic), clustering
- Entities & relations: named-entity extraction, structured event tuples (Actor/Action/Object)
- Text quality/source: readability, source reliability, duplication/novelty detection,
  multi-source triangulation (same event on N sources)
- Temporal patterns in text alone: news velocity/spike (articles per hour)

Output: features describing *what the news is about* — nothing about the market yet.

See `L1-methods.md` for the full detail.

## Level 2 — News text + ML models (text → richer features)

ML applied *to the text itself*, no price involved:

- Supervised classification: train a model to label news → event type, category, sentiment
- Embedding models: FinBERT/BERT/RoBERTa/DeBERTa dense vectors as text representations
- Ensemble classifiers (SVM/RF/LR stacking over multiple sentiment models)
- Sequence models: LSTM/Transformer over headlines
- Unsupervised ML: topic clustering, anomaly detection
- Structured event extraction: LLM models producing event-type + impact subject + horizon + confidence

Output: richer features (embedding vectors, predicted class probabilities).
Validation is on the **text task** (e.g., classification F1), not market prediction.
This is a feature-enrichment step, not a strategy.

See `L2-methods.md` for the real-world methods survey.

## Level 3 — News text + stock price (statistics, no ML)

The event-study / statistical layer — links news to price *without prediction*:

- Event study: align news timestamp → price window → abnormal return, CAR, significance
- Timestamp alignment rules: pre-close news → same day; after-close → next trading day
- Conditional stats: group news by keyword category → average abnormal return per category,
  hit rate of direction per category
- Granger causality: does news volume/sentiment precede returns?
- Leak vs surprise: pre-event CAR vs post-event CAR sign comparison
- Baseline comparison: news-day return distribution vs normal-day distribution
- Volatility response: does news change realized volatility/volume?

Output: **evidence** (which news types actually move prices) + **ground-truth labels**
(e.g., significant-abnormal-return events). No predictive model — this is what justifies
which features are worth using.

See `L3-methods.md` for the full detail.

## Level 4 — News text + stock price + ML (full prediction)

Combine everything, target = future price movement:

- Feature matrix: L1/L2 text features + L3-derived features + price/technical features
- Targets: direction (up/down), magnitude, volatility, abnormal-return significance
- Models: logistic regression → XGBoost/LightGBM/RF → deep fusion
  (transformer + news cross-attention, gated fusion that opens to news only
  when it adds value beyond price)
- Evaluation: out-of-sample IC, direction accuracy, backtest Sharpe
- Strategy layer: when to enter/exit based on predicted reaction

Output: a predictive model, honestly evaluated out-of-sample.

See `L4-methods.md` for the full detail.

## The key dependency

**L3 tells you which news features matter; L4 uses only those to predict.**
L1/L2 produce candidates; L3 filters them; L4 assembles the model.

## Which levels need price data?

| Level | Needs price? | Where it lives in this project |
|---|---|---|
| L1 | No — pure text | vinu-news enrichment |
| L2 | No — text + ML | vinu-news enrichment (learned features) |
| L3 | Yes — text + price | vinu-initial-analysis (`impact.py`, `significance_model.py`, `granger.py`) |
| L4 | Yes — text + price + ML | vinu-initial-analysis (`ml_model_pipeline`) |

The vinu-news enrichment features are pure text — no price needed there. Price only
enters at the validation/prediction stage, which lives in vinu-initial-analysis.

## Relation to the methods/ folder

`../methods/` holds 8 candidate methods, all of which are **L1/L2** (pure text, no
price needed). The L3/L4 machinery already exists and is rigorous
(`news_price_causality/impact.py`, `significance_model.py`); the missing piece is the
L1/L2 feature layer feeding into it.
