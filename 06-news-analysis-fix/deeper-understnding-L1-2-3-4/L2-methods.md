---
name: L2-methods
status: discussion-phase
purpose: detail of Level 2 — news text + ML models, still no price. ML applied to the text itself to produce richer features. Includes the real-world methods survey from current (2025–2026) research.
---

# L2 — News Text + ML Models: Methods (Text → Richer Features)

## What L2 is

ML applied *to the text itself*. Output = richer features (embeddings, predicted
class probabilities, structured extractions). Validation is on the **text task**
(e.g., classification F1), not market prediction.

## Method families

### 1. Supervised text classification

Train a model to label news:
- event type, category, sentiment polarity
- Requires labeled training data (human-annotated, or label-from-future-return — see below)

### 2. Pretrained transformer embeddings

- FinBERT: BERT fine-tuned on financial text — the standard baseline
- BERT / RoBERTa / DeBERTa: general-purpose encoders, DeBERTa beats FinBERT on
  sentiment accuracy (~75%)
- Dense vectors (e.g. 768-dim) preserved instead of collapsing to a scalar score —
  this retains narrative nuance the scalar loses
- Embeddings can be further optimized with Siamese networks / contrastive learning

### 3. Ensemble classifiers

- Stack FinBERT + RoBERTa + DeBERTa outputs into an SVM/RF/LR meta-model
- Reported ~80% sentiment accuracy vs ~75% for the best single model

### 4. Sequence models

- LSTM / Transformer / CNN over headline sequences
- Captures word order and context

### 5. Unsupervised ML on text

- Topic clustering, anomaly/outlier news detection

### 6. LLM structured event extraction

Modern equivalent of L1's rule-based event tags, done with an LLM structured-output call:
- Extract 6 orthogonal dimensions: sentiment polarity, sentiment intensity,
  **event type**, **impact subject**, **time horizon**, **confidence**
- Example schema: `S × [-1,1] × E × C × H × [0,1]`
  where S = {pos, neg, neu}, E = {earnings, merger, policy, product, mgmt, macro, other},
  C = {company, industry, macro}, H = {short, long}

## Real-world methods survey (2025–2026 research)

### Transformer sentiment models are the workhorse

- FinBERT is the default baseline; DeBERTa/RoBERTa/LLaMA-3 beat it on accuracy
- Ensembling (FinBERT+RoBERTa+DeBERTa → SVM stack) reaches ~80% sentiment accuracy
- LLaMA-3 fine-tuned to predict the sign of future excess return = 78.2% accuracy
  and produced the only profitable long-short strategy in a 3.1M-article study —
  lexicon-based (dictionary) strategies lost 9%

### Key practice: label sentiment by future returns, not annotation

The most informative real-world setups train sentiment on the actual prediction
task: label = sign of cumulative excess return over the next 3 trading days
([n, n+2], excess over the market). This is supervised by *price* but trained as a
*text* model — a bridge toward L3/L4.

### Structured extraction beats scalar sentiment (the 2026 shift)

From "Beyond Sentiment: Structured Information Extraction from Financial News":
- FinBERT sentiment features: strong under nonlinear models (F1=0.576), weak under
  linear models (F1=0.230) — the sentiment→return relation is fundamentally nonlinear
- LLM-extracted structured features capture information *orthogonal* to sentiment:
  53.5% systematic disagreement between FinBERT and LLaMA event semantics
- Combining both: F1=0.600 vs 0.576 alone (p<0.0001) — consistent across all 7 event types
- Non-sentiment structural dimensions (event type, impact subject, time horizon,
  confidence) independently contribute +0.019 beyond FinBERT alone
- Event type alone = 16.5% of feature importance, comparable to sentiment's 21.3%
- Conclusion: compressing news into a single sentiment score incurs substantial
  information loss

### Daily aggregation of article-level scores

Multiple articles per day → daily feature set: daily sum (intensity), min/max
(most pessimistic/optimistic signals), majority-vote class, mean/confidence.

### Dense embeddings outperform scalar scores

- Transformer + Siamese-optimized embeddings: MSE 0.078 vs 0.199 for scalar sentiment
- Raw embeddings better than scalar; unfreezing FinBERT unstable; attention-weighted
  aggregation suffered "attention collapse" at financial signal-to-noise ratios

## Output of L2

Richer feature vectors per article/day: embedding vectors, predicted class
probabilities, structured (event type, impact subject, horizon, confidence).

## What L2 feeds

L2 features become candidate columns for the L3 validation layer and the L4
feature matrix.

## Notes for this project

- The existing sentiment scores (rule-based, FinBERT) are L1/L2 sentiment — the
  disproven-signal finding means the *direction* of sentiment alone carries no
  signal, but nonlinear ML + structured features may still extract value
- A supervised variant worth considering: train event-type/impact labeling against
  the project's own `ar_significant`/`car_1h` labels instead of pure keyword rules
