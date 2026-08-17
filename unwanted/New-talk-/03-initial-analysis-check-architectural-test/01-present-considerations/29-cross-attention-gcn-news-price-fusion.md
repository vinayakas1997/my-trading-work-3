---
name: cross-attention-gcn-news-price-fusion
status: candidate-not-implemented
purpose: reference note on a bidirectional cross-attention + GCN fusion architecture for news+price prediction, found via web search Aug 2026 — a concrete benchmarked alternative to the gated-fusion (GS-Fuse) approach already documented in L4-methods.md. Moved here from 03-claude-new-methods/ — survives both Final-implementation limitations (not an LLM call; text-encoder options range from 102M to 8B, so check which encoder variant against the 2-3GB cap).
---

# Bidirectional Cross-Attention + GCN News-Price Fusion

## Title / what it is

A neural fusion architecture for combining news and price across *multiple
stocks at once*: stock-name embeddings are used inside the attention
mechanism so the model learns which news is relevant to which stock,
bidirectional cross-attention runs between price and news representations
(news attends to price, price attends to news), a 2-layer Graph
Convolutional Network models the interaction between the fused
representations of different stocks, and the outputs are combined via
weighted averaging. Reported result: 7.11% MAE reduction vs. baseline.

## Explanation — how it works

1. Compute news embeddings (from any L1/L2 method — this architecture is
   about the fusion step, not the text-feature step).
2. Compute stock-name embeddings, used to route/weight which news applies to
   which ticker within the attention mechanism.
3. Bidirectional cross-attention layer: price attends to relevant news, news
   attends to relevant price context.
4. A 2-layer GCN models cross-stock interaction on top of the fused
   representations — this is the part that generalizes beyond a single
   ticker at a time.
5. Multiple fused representations combined via weighted average into the
   final prediction.

## Input

Two things simultaneously, for **multiple stocks at once**: a set of
news articles (embedded) per stock, and a 20-trading-day historical price
window per stock — plus the same for every other stock in the batch,
since the GCN layer needs the joint multi-stock input to model
cross-stock interaction.

## Output format

A predicted price/return value per stock (regression), evaluated via
MAE — the fusion architecture outputs one prediction per ticker, informed
jointly by that ticker's news and its cross-stock GCN context.

## Impact — what can be extracted

A second, concretely benchmarked reference architecture for the L4
news+price fusion layer, alongside the gated-fusion (GS-Fuse) approach
already documented in
`../../01-news-analysis-methods/deeper-understnding-L1-2-3-4/L4-methods.md`.
Notably this one is inherently **multi-stock** (via the GCN layer), whereas
GS-Fuse as documented is per-ticker — relevant if cross-ticker structure
ever becomes part of the news+price angle, not just `peer_relative_strength`.

## Is it LLM-dependent?

No. This is a trained neural architecture (attention + GCN) — it *consumes*
text embeddings as input features, which could come from an LLM-based or
non-LLM L1/L2 method, but the fusion architecture itself is not an LLM call.

## Model size / base model (from source)

The paper specifies different backbones per dataset:
- **Taiwan market (TW21) experiments**: backbone LLM is **LLaMA3-8b**
  (`Llama3-TAIDE-LX-8B-Chat-Alpha1`, 8B parameters — **fails the 2-3GB
  cap**); an alternative configuration uses **CKIP's GPT-2**
  (`gpt2-base-chinese`, 102M parameters — **fits comfortably**).
- **U.S. market (BigData23) experiments**: **LLaMA2** and **OpenAI's GPT-2**,
  following the Time-LLM paper's configuration (exact parameter variant not
  restated in this paper — LLaMA2 would fail the cap, GPT-2 would fit).
- **Text encoding**: each news article is encoded independently with a
  pre-trained **BERT or DeBERTa** model (base-size not explicitly stated —
  base variants of both fit comfortably under the cap).
- **Architecture**: 2-layer GCN + CausalCNN for temporal aggregation,
  bidirectional cross-attention, 20-trading-day input window; the fused
  embedding dimension is left as a symbolic *d*, not a stated number.

**For this project's US tickers (AAPL/TSLA/JNJ)**: use the GPT-2/BERT/
DeBERTa encoder configuration, not LLaMA2/LLaMA3-8B, to stay under
limitation #2.

## Data sources needed

News text (embedded, from whichever L1/L2 method produces the input
vectors) + price, across multiple stocks simultaneously — the GCN layer is
specifically what requires more than one ticker's data to be useful.

## Fit with existing project structure

An alternative to the multimodal fusion models already listed in
`../../01-news-analysis-methods/deeper-understnding-L1-2-3-4/L4-methods.md`
(transformer + news cross-attention, gated fusion). Also relevant to
`peer_relative_strength` given its inherently cross-stock design via the
GCN layer.

## Source

- [Generalized Stock Price Prediction for Multiple Stocks Combined with News Fusion](https://arxiv.org/abs/2603.19286) — `arXiv:2603.19286`
