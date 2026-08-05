---
name: differnt-combination-analysis
status: discussion-phase
purpose: the different combination studies for market analysis — price-only, news-only, news+price, and price+other-data. Maps each combination to where it lives in the vinu project.
---

# Different Combination Analysis — News, Price, and Everything in Between

## The core idea

There are several ways to analyze a market, distinguished by **which data
sources** are combined. The news research (L1–L4) and the price research
(Kronos/TSFM) are two families; the interesting layer is what happens when you
*combine* them, and what else price can be combined with beyond news.

```
price only                    → Kronos / TSFM / technical models
news only                     → L1 (text) / L2 (text + ML)
news + price                  → L3 (event study) / L4 (ML prediction)
price + other data            → macro, fundamentals, social, peers, order flow
```

## The explanation — news+price is L3/L4, but there are other combinations

### 1. News+price combination = L3/L4 — yes, and it IS the popular direction

The news+price combination is exactly what L3 (statistics) and L4 (ML prediction)
define. It's the most-studied combination in the field:

- Event study + abnormal returns (L3)
- FinBERT/news features → XGBoost/Transformer → predict returns (L4)
- Gated/multimodal fusion (GS-Fuse, multimodal transformers)

So "news+price = L4, that's it" is **correct** for the news-specific combination.
The `news_price_causality` angle already IS this combination in the project.

### 2. But there are OTHER combinations beyond news+price

Price is combined with *many* data sources in the literature, not just news:

| Combination | What it is | In vinu today? |
|---|---|---|
| price + news | news features → predict price | yes — `news_price_causality` |
| price + volume/order flow | generative market simulators (MarketGPT, MarS) | partial — `ml_model_pipeline` uses volume |
| price + fundamentals | SEC filings + news + price (multi-stage LLM funnel) | no |
| price + macro | TVP-VAR spillover matrices + transformer | seed of it — `regime_analysis` |
| price + social sentiment | FinGPT on Twitter/StockTwits | no |
| price + cross-asset/peers | iTransformer variate-tokens, node-transformer with sector graph | partial — `peer_relative_strength` |
| price + options | implied volatility, put/call ratios, options flow | tooling only — `options_tool.py` + `options-trading` skill |
| price + crypto on-chain (crypto only) | chain activity, whale moves, on-chain flow | tooling only — `crypto-analysis` skill |
| price + earnings/fundamentals calendar | scheduled events vs. surprise | no — worth adding later |

### 3. And the combination DIRECTION matters too

- **news→price**: news predicts price (the popular direction)
- **price→news**: does a price move *precede* the news — leakage detection
- **bidirectional**: Granger causality — `granger.py` already does both directions

## Combination 1 — Price only

Predict from price/K-line data alone.

- Kronos: foundation model trained on 12B K-lines from 45 exchanges — predicts
  next K-line, volatility, synthetic data
- TSFMs: Chronos, TimesFM, TimeGPT, MOIRAI, MOMENT, PatchFormer
- Financial transformers: PatchTST, iTransformer, TFT, LPatchTST
- Classical: ARIMA, GARCH (volatility), Kalman filters, exponential smoothing

Caveat: research metrics (MSE/IC) don't equal tradable alpha; directional accuracy
in the field is ~50–54%.

## Combination 2 — News only

Analyze the news text itself, no price involved.

- L1 (text): keywords, event-type rules, entities, TF-IDF, triangulation, velocity
- L2 (text + ML): FinBERT/DeBERTa sentiment, ensembles, structured event
  extraction, embeddings

These produce features describing *what the news is about*.

## Combination 3 — News + price (the popular one)

The most-studied combination. News features → explain/predict price movement.

- **L3 (statistics, no ML)**: event study, abnormal returns / CAR, timestamp→price
  alignment, Granger causality, leak-vs-surprise detection
- **L4 (ML prediction)**: news features + price features → model → future returns
  (direction, magnitude, volatility). Models: XGBoost, LSTM, transformers,
  gated/multimodal fusion (GS-Fuse)
- Combination *direction* matters:
  - news→price (news predicts price — the popular direction)
  - price→news (does price move *precede* news — leakage)
  - bidirectional (Granger causality)

This is exactly what the `news_price_causality` angle in vinu-initial-analysis is.

## Combination 4 — Price + other data (beyond news)

The same fusion pattern applies to other data sources:

| Combination | What it is | In vinu today? |
|---|---|---|
| price + news | news features → predict price | yes — `news_price_causality` |
| price + volume/order flow | generative market simulators (MarketGPT, MarS) | partial — `ml_model_pipeline` uses volume |
| price + fundamentals | SEC filings + news + price (multi-stage LLM funnel) | no |
| price + macro | TVP-VAR spillover matrices + transformer | seed of it — `regime_analysis` |
| price + social sentiment | FinGPT on Twitter/StockTwits | no |
| price + cross-asset/peers | iTransformer variate-tokens, node-transformer with sector graph | partial — `peer_relative_strength` |
| price + options | implied volatility, put/call ratios, options flow | tooling only — `options_tool.py` + `options-trading` skill |
| price + crypto on-chain (crypto only) | chain activity, whale moves, on-chain flow | tooling only — `crypto-analysis` skill |
| price + earnings/fundamentals calendar | scheduled events vs. surprise | no — worth adding later |

### 4. Three more combinations genuinely worth adding (detail)

#### price + options

- **What it is**: combine price with options-market data — implied volatility,
  put/call ratios, options flow, open interest, IV skew/term structure
- **Why it matters**: options are a forward-looking market; IV/flow can signal
  sentiment and positioning before the price moves
- **In vinu today**: tooling only — `options_tool.py` and the `options-trading`
  skill exist in vinu-agent, but there is no dedicated analysis angle using them
- **Candidate angle**: a `options_signal` angle reading implied vol / put-call
  ratios and feeding the agent alongside price+news

#### price + crypto on-chain (crypto only)

- **What it is**: combine price with blockchain on-chain data — exchange flows,
  whale/market-maker moves, active addresses, stablecoin flows, funding rates
- **Why it matters**: on-chain data is unique to crypto and captures the actual
  positioning of holders, not just traded price
- **In vinu today**: tooling only — a `crypto-analysis` skill exists; only matters
  if trading crypto assets
- **Candidate angle**: a `onchain_signal` angle used only for crypto symbols

#### price + earnings/fundamentals calendar

- **What it is**: combine price with scheduled corporate events — earnings dates,
  dividend dates, economic releases — separating scheduled events from surprises
- **Why it matters**: scheduled events behave differently from surprises (the PLOS
  study already treated scheduled earnings as a special case); a calendar lets the
  agent know a move is "expected" vs "unexpected"
- **In vinu today**: not built — worth adding later as a `event_calendar` feature
  feeding `news_price_causality` and the report

## The pattern that generalizes

Every angle in vinu is one cell of this matrix — a combination of data sources
focused on one question:

- `news_price_causality` = price + news
- `regime_analysis` = price + regime/state
- `peer_relative_strength` = price + cross-asset
- `ml_model_pipeline` = price + price-derived features (+ optional news)
- Kronos-style future angle = price alone

## Recommendation for the project

- **News + price (L3/L4) is the right first build** — it's the popular,
  well-validated combination, and the machinery already exists
  (`impact.py`, `significance_model.py`, `ml_model_pipeline`).
- Don't expand scope beyond it for the news fix. The other combinations
  (macro, fundamentals, social) are future angles, not this task.
- One genuinely useful deepening: Granger/leak detection — tells the agent
  whether news *causes* moves or *reacts* to them.

## Related files

- `../01-news-analysis-methods/` — news research (L1–L4)
- `../02-price-analysis-methods/` — price research (Kronos, TSFM)
- `project-explanation.md` (same folder) — the project picture and phases
