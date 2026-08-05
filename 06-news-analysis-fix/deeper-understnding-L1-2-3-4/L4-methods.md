---
name: L4-methods
status: discussion-phase
purpose: detail of Level 4 — news text + stock price + ML. Combines L1/L2 text features with L3-derived labels and price/technical features into a predictive model, honestly evaluated out-of-sample.
---

# L4 — News Text + Stock Price + ML: Methods (Full Prediction)

## What L4 is

Combine everything, target = future price movement. L1/L2 produce the text feature
candidates, L3 produces evidence + ground-truth labels, L4 assembles a predictive
model and evaluates it out-of-sample.

## Method families

### 1. Feature matrix construction

- L1/L2 text features: sentiment scores, event-type tags, entities, embeddings
- L3-derived features: `ar_significant`, `car_1h`, category-conditional statistics
- Price/technical features: lagged returns, SMA, volatility, volume ratio
- Text features aggregated to the price-bar timeline (daily or intraday)

### 2. Prediction targets

- Direction (up/down) — classification
- Magnitude (return size) — regression
- Volatility — regression
- Abnormal-return significance — classification against `ar_significant`

### 3. Model families (in increasing sophistication)

1. **Linear baselines**: logistic regression, linear regression
2. **Tree ensembles**: XGBoost, LightGBM, Random Forest — the industry workhorse,
   robust to nonlinear text features, works with SHAP for interpretability
3. **Deep sequence models**: LSTM, GRU, CNN-LSTM, attention-LSTM
4. **Patch/transformer time-series models**: PatchTST, TimesNet, tPatchGNN
5. **Multimodal fusion**:
   - Transformer + news cross-attention (news attends to price and vice versa)
   - Gated fusion: open the text channel only when it adds predictive value beyond
     historical prices (GS-Fuse, Granger-supervised gating)
   - Node transformer with graph structure across stocks (sector/supply-chain edges)

### 4. Evaluation discipline

- Out-of-sample / chronological split (train → validation → test, no window overlap)
- Metrics: IC (information coefficient), direction accuracy, F1/AUC, backtest Sharpe
- Honest evaluation under trading constraints (transaction costs, participation limits)
- Leak prevention: no look-ahead bias, labels don't cross split boundaries

## Real-world research findings (2025–2026)

### Nonlinearity matters

- FinBERT sentiment features: strong under nonlinear models (F1=0.576), weak under
  linear (F1=0.230) — sentiment→return is fundamentally nonlinear
- Tree ensembles and deep models capture this; linear models waste the signal

### Sentiment + technical fusion works

- FinBERT features + technical indicators into XGBoost with SHAP:
  FinBERT features rank among the most influential predictors
- Fusion of FinBERT sentiment + wavelet-processed prices via CNN-LSTM:
  multimodal > single-modality

### LLM sentiment + deep time-series

- FinGPT sentiment + price + technicals into attention-LSTM/CNN hybrids:
  sentiment significantly improves forecasting across all tested architectures
- Sentiment models benefit some architectures more than others:
  PatchTST/TimesNet regression gains; LSTM/tPatchGNN barely affected

### Gating is the principled approach

- Only let news text in when it adds value beyond price history
- GS-Fuse: Granger-supervised gated fusion — the gate learns when text matters

## Recommended practical stack (industry-practical)

- XGBoost with SHAP is the realistic choice: handles mixed text+price features,
  is interpretable, needs modest data
- Multimodal deep fusion (transformer + cross-attention / gated fusion) is the
  research frontier but needs substantially more data and compute

## This project's existing L4 machinery

- `ml_model_pipeline/compute.py`: trains 9 regressors, OOS IC evaluation,
  target = next-bar return
- Current news features are only `sentiment_score` + `impact_label`
  (`compute.py:102-108`) — the natural place to feed validated L1/L2 features

## The build direction this implies

1. L1/L2: build event-type + entity features in vinu-news (pure text)
2. L3: validate which features predict `ar_significant`/`car_1h`
3. L4: feed the validated features into `ml_model_pipeline`, evaluate OOS IC
4. Gate the agent's `adverse_news_catalyst` exit rule on a validated feature,
   not the disproven bearish-sentiment signal
