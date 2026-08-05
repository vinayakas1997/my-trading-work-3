---
name: hybrid-llm-price-fusion
status: candidate-not-implemented
purpose: full writeup of the "Hybrid LLM + price" fusion family, previously only a 4-line bullet summary in 02-price-analysis-methods.md's section 4 without its own citation. Parked here directly (never lived in 03-claude-new-methods) because it fails Final-implementation limitation #1 (no LLM implementation for now).
---

# Hybrid LLM + Price Fusion — LLM as a Market-Signal Generator

## Title / what it is

A hybrid architecture that treats an LLM as a **mathematically-defined signal
generator**: it reads financial news and extracts a directional market
sentiment plus a confidence score, which is then fused with structured
historical price features through a **noise-robust gating mechanism**,
letting a Transformer adaptively weigh semantic (text) vs. quantitative
(price) information. This is the price-prediction-side cousin of the
news-side gated fusion already documented in
`../../01-news-analysis-methods/deeper-understnding-L1-2-3-4/L4-methods.md`
(GS-Fuse) — same gating idea, but the LLM's role here is narrower and more
explicit: produce a (direction, confidence) pair, not a general embedding.

## Explanation — how it works

1. An LLM reads financial news and outputs a directional sentiment signal
   (up/down/neutral-style) with an associated confidence score — a much
   narrower, more structured output than a general text embedding.
2. A gating mechanism weights this LLM signal's contribution based on
   contextual relevance and the LLM's own stated confidence — this is what
   makes it "noise-robust": low-confidence or contextually-irrelevant LLM
   signals get down-weighted rather than blindly fused in.
3. The gated LLM signal is fused with structured historical price features
   inside a Transformer architecture.
4. Reported result: **RMSE reduced 5.28% vs. a vanilla Transformer baseline**
   (Hybrid RMSE = 114.66 vs. Vanilla RMSE = 121.05; p = 0.003, Cohen's d =
   0.85) — a real, statistically-tested effect size, not just a point
   estimate.
5. **Robustness finding**: under injected noise (σ = 0.20), the Hybrid model
   retains 94% of its baseline performance vs. 89% for the vanilla
   Transformer — the gating mechanism appears to help specifically because
   it can suppress a noisy/low-confidence LLM signal rather than being stuck
   fusing it in unconditionally.

## Input

News text (granularity — single article vs. a daily-aggregated batch —
not specified in the abstract; the paper generically says the LLM "reads
financial news") plus a structured historical price-feature window for
the Transformer fusion step.

## Output format

Two layers: the LLM step outputs a **(direction, confidence)** pair (e.g.
bullish/bearish + a confidence float); the full pipeline's final output
is a fused price forecast (point value), evaluated via RMSE.

## Impact — what can be extracted

A concrete, benchmarked alternative fusion pattern for the L4 news+price
layer, distinct from both GS-Fuse (news-side gated fusion, already
documented) and the cross-attention+GCN architecture
(`../../03-claude-new-methods/cross-attention-gcn-news-price-fusion.md`).
The specific contribution here is treating the **LLM's own confidence
score** as the gating signal, rather than learning the gate purely from
data — a more interpretable design (you can inspect why a given day's LLM
signal was down-weighted) at the cost of depending on the LLM's confidence
calibration being trustworthy in the first place.

## Is it LLM-dependent?

Yes — the signal-generation step is fundamentally an LLM call (reading news,
producing a directional + confidence output). The gating and Transformer
fusion machinery downstream are standard trained-model components, not
LLM-dependent themselves, but the pipeline as a whole requires the LLM step
to produce its input.

**This is why it's parked here**: Final-implementation limitation #1 rules
out any LLM-dependent method for now — revisit once that limitation lifts.

## Model size / base model (from source)

**Not disclosed.** The abstract refers only to "a Large Language Model
(LLM)" and "a prompt-based LLM" functioning as the signal generator — no
specific model name (GPT-4, GPT-3.5, LLaMA, FinBERT, etc.) or parameter
count is given at the abstract level. Would need the full paper's methods
section to pin this down; not yet checked.

## Data sources needed

News text (for the LLM signal-generation step) + price/technical features
(for the Transformer fusion step) — both required simultaneously, same
"Bucket B" classification as the cross-attention+GCN fusion method: this
can't run on news alone or price alone, and can't be computed purely at
ingest time the way L1/L2 news-only methods can.

## Fit with existing project structure

Originally only a 4-line unsourced bullet in
`../../02-price-analysis-methods/price-analysis-methods.md` section 4
("Hybrid LLM + price (the fusion family)") — this file is the expanded,
sourced version of that bullet, following a dedicated search to find its
actual paper. Alternative to GS-Fuse (`L4-methods.md`) and to
`cross-attention-gcn-news-price-fusion.md` for the same news+price fusion
slot — three different fusion designs now documented for the same L4
problem, worth comparing once LLM implementation is back in scope.

## Source

- [Improving Financial Forecasting with a Synergistic LLM-Transformer Architecture: A Hybrid Approach to Stock Price Prediction](https://arxiv.org/abs/2601.02878) — `arXiv:2601.02878`
