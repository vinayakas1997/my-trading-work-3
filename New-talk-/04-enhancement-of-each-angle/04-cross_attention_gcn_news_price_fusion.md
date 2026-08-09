---
name: angle-04-cross_attention_gcn_news_price_fusion
status: decided
purpose: discussion and enhancement proposal for the `cross_attention_gcn_news_price_fusion` angle. Reference implementation lives at `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/cross_attention_gcn_news_price_fusion/`.
---

# 04 — cross_attention_gcn_news_price_fusion

**Title (from spec.yaml):** Bidirectional Cross-Attention + GCN News-Price Fusion

## 1) Status

- Discussed: 2026-08-07
- Status: decided (current state understood and documented; not backtestable
  as-is — see §3/§7 for why)
- Reference implementation verified against real code: `compute.py` / `spec.yaml` at
  `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/cross_attention_gcn_news_price_fusion/`
- This is **not an implementation plan** — no build work is happening now.
  We will train a real version of this ourselves in the future; for now
  this file documents what exists, what's real vs. degenerate in the
  current code, and the real research this idea is grounded in.

## 2) One-line definition

An idea for combining news and price data using two AI techniques —
"cross-attention" (news and price data each get to look at each other
before making a prediction) and a "graph neural network" (which is
supposed to learn how different stocks move together) — but the version
in the code today only has the first piece working for real; the second
piece and the training step are both missing.

## 3) Decided parameters / current-state facts

| Item | Current reality | Notes |
|---|---|---|
| Cross-attention module | real, genuine PyTorch bidirectional attention | price attends to news, news attends to price — this part actually works as designed |
| GCN (graph) module | structurally degenerate — a no-op | `compute()` only ever runs on one symbol at a time, so the "graph" is a single node with a self-loop; mathematically an identity pass, not real cross-stock modeling. Code is honest about this (`gcn_note` field). |
| News/text feature | bag-of-words (word counts from titles) | not a real language-understanding model, a simple stand-in |
| Model training | none — weights are randomly initialized once and never updated | `model_backend: "trained_in_process"` is misleading-sounding; there is no actual training loop, no loss function, no learning from data |
| Is this angle backtestable today in the ARIMA/Chronos sense? | No | since predictions come from an untrained (random) network, a hit-rate backtest would just measure noise, not real forecasting skill — decided not to force this into the same walk-forward framework yet |
| Grounded in real research? | Yes | closest match: *"Generalized Stock Price Prediction for Multiple Stocks Combined with News Fusion"* (arXiv 2603.19286, Liao/Lee/Cheng/Chen/Lee/Wang, March 2026) — uses the same bidirectional cross-attention + 2-layer GCN combination, reports 7.11% MAE reduction vs. baseline |
| Is the paper's model available to download? | No | no GitHub repo or pretrained checkpoint found for this paper — unlike Chronos/Kronos, there is nothing to just plug in; a real version would have to be built and trained from scratch, using the paper as an architectural reference |
| What's missing vs. the paper | (1) multi-ticker input so the GCN has real cross-stock structure to learn from, (2) an actual training loop with labeled outcomes | both are future build work, not decided/scoped here |
| Timeframes | 1min, 5min, 15min, 1H, 4H, 1D — **decided as the target set for whenever this angle is actually built**, same as every other angle | not meaningful today: with an untrained/random model there is nothing real to backtest at any timeframe (see row above), so this is a forward-looking decision to apply once real multi-ticker training exists, not something being validated now |

## 4) Example — what today's output actually looks like

```
symbol: AAPL
model_backend: trained_in_process
gcn_note: "The spec's GCN layer needs multiple stocks jointly; compute() here
           is called for a single symbol at a time (no multi-ticker batching
           in this interface), so the GCN degenerates to a 1-node self-loop
           graph (an identity pass) rather than modeling real cross-stock
           structure."
n_news_articles_used: 4
price_window: 20
text_feature: bag_of_words
last_close: 142.30
predicted_next_return: 0.0031
predicted_next_close: 142.74
```

Every field here is real code output — the point of showing it is that
`predicted_next_return` is the output of a random, never-trained network,
so this number should not be read as a real forecast today.

## 5) Storage, querying, API shape

Not decided here — this angle isn't ready for the walk-forward
backtest/tagging pipeline used by ARIMA/Chronos, since its current
predictions carry no real signal to measure. Once a trained,
multi-ticker version exists, it should plug into the same shared
[common-rule-of-time-slicing-tags.md](common-rule-of-time-slicing-tags.md)
machinery as every other angle — no new storage design is expected to be
needed at that point, just deferred until there's something real to
store.

## 6) What we will achieve / how to use it

- Not applicable yet in the "which timeframe is this most reliable at"
  sense — that question only becomes meaningful once the model is
  actually trained.
- What this discussion achieves now: an honest record of what's real
  (cross-attention module, architecture) vs. what's missing (GCN's
  cross-stock input, training) vs. what's just a stand-in (bag-of-words
  text feature) — so future work knows exactly what to build rather than
  assuming the current code is further along than it is.
- Confirms the underlying idea is worth pursuing — real published
  research using the same core combination (cross-attention + GCN news-
  price fusion) reports a meaningful accuracy improvement over baseline.

## 7) Deeper rationale

**Why this angle isn't backtested the same way as ARIMA/Chronos:** those
two produce predictions from something real — a fitted statistical model,
or a genuinely pretrained neural network. This angle's network has
random, never-learned weights, so its predictions are structurally no
different from noise. Running a walk-forward hit-rate backtest on random
noise would produce a number that looks like a real evaluation but means
nothing — worse than not testing at all, since it could be mistaken for a
real result. Better to be explicit that this needs training first.

**Why the GCN is degenerate, and why that's not a small detail:** the
whole point of the GCN layer, per both this angle's own spec and the
matching research paper, is to model how *multiple stocks* move in
relation to each other. The current `compute()` interface processes one
symbol at a time with no access to other tickers' data, so there is
nothing for a graph layer to operate on — it's mathematically forced into
a single self-loop, which is an identity function. This isn't a minor
approximation, it's the entire cross-stock modeling capability being
absent.

**Why we searched for and cited real research instead of just describing
the code:** the code's own docstring already frames this as a
"structurally reduced" demonstration, not a finished model — verifying
whether the underlying idea has real merit (rather than just being an
untested guess) was worth doing before deciding whether "train this for
real later" is worth prioritizing. The match found (arXiv 2603.19286)
confirms the combination has real, measured value (7.11% MAE reduction)
when actually implemented with multi-ticker input and real training —
which is exactly what's missing here.

**Open/unresolved, explicitly deferred to future work:** building a real
multi-ticker input path and a real training loop (with labeled
next-return outcomes) is out of scope for this documentation pass. This
file's job was to establish ground truth on current state and confirm the
idea is worth eventually building — not to design that build.
