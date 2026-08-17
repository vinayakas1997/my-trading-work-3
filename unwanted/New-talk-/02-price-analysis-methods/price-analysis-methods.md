---
name: price-analysis-methods
status: discussion-phase
purpose: the price-based analysis landscape — what the latest methods/models predict from price/K-line data alone (the "Kronos" family and its neighbors), organized like the news L1-L4 taxonomy, so they can become future angles alongside the news angle.
---

# Price-Based Analysis Methods — What the Latest Models Predict from Price Alone

## What this covers

The news research (`../01-news-analysis-methods/`) covers what can be extracted from
news text (L1–L4). This file is the parallel treatment for **price data alone** —
what the current (2025–2026) methods/models predict from price/K-line data, with no
text input. These become candidate future angles for vinu-initial-analysis.

## 1. Kronos — the flagship (AAAI 2026, open-source)

- **What it is**: the first open-source foundation model trained *only on financial
  K-lines*. Pre-trained on **12 billion K-line records from 45 global exchanges**
  across 7 time granularities.
- **How it works**: a specialized tokenizer discretizes OHLCVA (open/high/low/
  close/volume/amount) into hierarchical tokens → an autoregressive decoder-only
  Transformer predicts the next K-line (like GPT predicts the next word).
- **Claims**:
  - +93% RankIC over the leading time-series foundation model (TSFM)
  - +87% over the best non-pretrained baseline
  - −9% MAE in volatility forecasting
  - +22% generative fidelity for synthetic K-line sequences
  - Zero-shot works across unseen markets; fine-tuning improves further
- **Sizes**: Kronos-mini (4M params) → Kronos-large (499M), all on HuggingFace
  (NeoQuasar). Context 512–2048.
- **The critical caveat** (independent review): benchmarks are **MSE/CRPS —
  statistical, not economic**. Directional accuracy is barely above 50% in general.
  Trained on noise-rich data, it may learn "the shape of noise, not exploitable
  alpha." Its most defensible value today: **synthetic data generation + zero-shot
  forecasts** — not a live-trading signal yet.

## 2. Time Series Foundation Models (TSFMs — the general-purpose family)

- Chronos (Amazon), TimesFM (Google), TimeGPT, MOIRAI, MOMENT, Timer/Timer-XL,
  Lag-Llama, PatchFormer
- All are pretrained transformers over generic time series
- **Key finding**: general TSFMs often **UNDERPERFORM specialized financial models
  (e.g. iTransformer) on K-line data** — that's precisely why Kronos exists

## 3. Transformer architectures that actually win on finance (trained from scratch)

| Model | Directional acc (reported) | Strength |
|---|---|---|
| DLinear | ~50% | mean-reversion, simple linear |
| LSTM | ~51% | sequential nonlinearity |
| PatchTST | ~50% | channel independence = regularizer |
| iTransformer | ~50% | cross-asset correlations (macro links) |
| TFT (Temporal Fusion Transformer) | ~53% | variable-selection filters noise |
| LPatchTST (LSTM+PatchTST) | ~54% | best downside robustness, Sharpe 2.31–2.32 |

**Takeaway**: better statistical forecast ≠ better returns. Sharpe-strong models
(TFT, LPatchTST) win on risk-adjusted terms, not RMSE.

## 4. Hybrid LLM + price (the fusion family)

- LLM used as a signal generator (directional sentiment + confidence score)
- Gated fusion into a Transformer with price features
- Result: RMSE −5.28% vs vanilla Transformer baseline (p = 0.003)
- This is the price-side cousin of the news-side gated fusion (GS-Fuse)

## 5. Regime-aware transformers

- **TIPS** (Transformer with Inductive Prior Synthesis): adapts temporal inductive
  biases to changing market regimes (momentum vs mean-reversion)
- **Notable finding**: no single architecture dominates all markets; lightweight
  LSTM/GRU/Mamba often beat huge transformers on financial data
- The performance gap comes from structural constraints (which temporal
  dependencies are emphasized), not model capacity

## 6. Classical statistical (still the baselines)

- ARIMA, GARCH (volatility), Kalman filters, exponential smoothing
- Kronos is benchmarked against these; for volatility specifically, GARCH remains
  the transparent parametric alternative

## How this maps to the vinu angles

Price-only analysis = one *family* of future angles, alongside the news angle:

- **Kronos/TSFM zero-shot forecasts** → a new `kronos_forecast`-style angle (price prediction)
- **TFT/LPatchTST** → enhance `ml_model_pipeline` (regressors → temporal fusion)
- **iTransformer cross-asset** → extends `peer_relative_strength` (cross-stock/cross-index links)
- **Regime-aware models** → feeds `regime_analysis` (already exists)
- **Synthetic K-line generation** → backtest stress-testing (`backtesting_44_metrics`)

## The same honest caveat as news

Research metrics (MSE/IC) don't equal tradable alpha. The directional accuracy
ceiling of ~50–54% holds for price-only methods too — they capture volatility
clustering (a risk characteristic), not necessarily conditional mean predictability
(an alpha characteristic).

## Sources

- Kronos: AAAI 2026, arXiv:2508.02739, github.com/shiyu-coder/Kronos
- Foundation Models for Time Series survey (arXiv:2504.04011)
- TIPS: arXiv:2603.16985
- iTransformer: ICLR 2024
- PatchFormer: arXiv:2601.20845
- Jonathan Kinlay — "Time Series Foundation Models for Financial Markets"
- Various 2025–2026 transformer/LLM-finance papers (see discussion)
