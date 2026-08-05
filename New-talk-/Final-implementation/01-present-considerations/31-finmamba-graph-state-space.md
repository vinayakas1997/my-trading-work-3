---
name: finmamba-graph-state-space
status: candidate-not-implemented
purpose: reference note on FinMamba, a Mamba (state-space model) architecture for stock movement prediction, found via web search Aug 2026 — a different architecture family than everything else catalogued. Moved here from 03-claude-new-methods/ — survives Final-implementation limitation #1 (not an LLM); size unconfirmed for limitation #2.
---

# FinMamba — Graph-Enhanced Mamba for Stock Movement

## Title / what it is

A stock-movement prediction model using a **Mamba** (state-space model, SSM)
backbone instead of a Transformer, combined with a market-aware graph
structure across stocks. Every trained-from-scratch model catalogued in
`18-dlinear.md` through `23-lpatchtst.md` is either transformer-based or a
simple linear/recurrent baseline — this is a genuinely different
sequence-modeling family, not represented at all in that comparison.

## Explanation — how it works

State-space models (the Mamba architecture specifically) process sequences
with linear-time complexity rather than attention's quadratic cost, which
generally makes them cheaper to run at long sequence lengths and gives them
different long-range-dependency handling characteristics than attention.
FinMamba adds a market-aware graph layer on top, so cross-stock structure
(similar in spirit to `peer_relative_strength` / `21-itransformer.md`'s
cross-asset angle) feeds into the SSM backbone rather than being handled
separately.

## Input

A 20-step historical price window across **multiple stocks
simultaneously**, connected via the market-aware graph structure — not a
single-ticker input.

## Output format

A stock movement prediction — framed as movement (up/down, or magnitude)
rather than a raw price forecast, per the paper's title; exact output
shape (classification vs. regression) not confirmed in this research
pass.

## Impact — what can be extracted

A candidate addition to the model-family comparison — not obviously better
than the existing options (no directional-accuracy figure was captured for
it in the search), but worth including in any future head-to-head
comparison given it's architecturally distinct from everything already
tested, and SSMs are reported elsewhere in the 2026 literature to sometimes
beat larger transformers on financial data specifically (`24-tips-regime-aware-transformer.md`
already flags this general pattern: "lightweight LSTM/GRU/Mamba often beat
huge transformers on financial data").

## Is it LLM-dependent?

No — a trained neural sequence model (state-space model + graph layer), same
general class as the other trained models here, not an LLM/text-generation
model.

## Model size / base model (from source)

No total parameter count disclosed in the accessible sections. The only
architecture specifics found: **2 GNN layers, 2 hierarchy levels, a
20-step window size** for the graph/Mamba backbone. Full parameter/hidden-
dimension details are referenced as living in the paper's appendix
(Sec. A.4), which wasn't captured in this extraction — check the appendix
directly before confirming this against the 2-3GB cap (limitation #2).

## Data sources needed

Price data + a cross-stock graph structure. No text/news.

## Fit with existing project structure

Candidate addition to the trained-from-scratch model comparison
(`18-dlinear.md` through `23-lpatchtst.md`), and relevant to
`peer_relative_strength` given its cross-stock graph component (same
relevance note as `21-itransformer.md`).

## Source

- [FinMamba: Market-Aware Graph Enhanced Multi-Level Mamba for Stock Movement Prediction](https://arxiv.org/abs/2502.06707) — `arXiv:2502.06707`
