---
name: limitations
status: discussion-phase
purpose: the fixed constraints scoping the Final-implementation phase for vinu — what's deliberately excluded or capped, so build decisions stay inside this boundary regardless of what the research/discussion-phase docs recommend.
---

# Vinu — Final Implementation Limitations

> **NOTE**: [`03-actual-plan-findings/`](03-actual-plan-findings/) holds the
> actual implementation plan and project analysis — always check that folder
> first for how the project is actually being built. This file and
> `01-present-considerations/` are the constraints and candidate-method inputs
> that feed the plan; they are not the plan itself.

> **NOTE**: all future discussion for this phase always relates back to
> [`01-present-considerations/`](01-present-considerations/) — that folder is
> where the methods that survive the limitations below live, along with the
> implementation plan and each method's full details. This file only defines
> the boundary (what's excluded/capped); it isn't itself the plan.

> **NOTE**: Methods/models excluded by the limitations below are not deleted
> from the research — they're moved to
> [`00-future-considerations/`](00-future-considerations/) (same folder) as
> candidates to revisit once a limitation lifts (e.g. once LLM implementation
> is in scope, or once the size cap is raised). Treat that folder as the
> parking lot for anything this file rules out, not as discarded work.

> These are hard constraints for this phase, not preferences. Any method or
> model surfaced in `../03-claude-new-methods/`, `../01-news-analysis-methods/`,
> or `../02-price-analysis-methods/` that violates one of these is **not
> eligible** for Final-implementation right now, even if it was flagged
> "recommended" or "most promising" in the discussion-phase docs.

## 1. No LLM implementation (for now)

Any method that requires an LLM call — structured-output extraction, LLM-based
event-type classification, agentic memory/reasoning, LLM-agent factor
research, etc. — is **not considered** in this implementation phase.

This rules out, from the research already catalogued:
- `llm-induced-event-taxonomy`
- `sec-8k-filing-event-extraction`
- `earnings-call-transcript-signal`
- `financial-knowledge-graph-extraction`
- `stockmem-event-reflection-memory` (already out-of-scope separately, as
  agent-layer work)
- `annual-report-llm-agent-factor-research` (already out-of-scope separately,
  as agent-layer work)

Keyword/rule/lexicon/classical-ML methods remain in scope — they don't
require an LLM call:
- `event-type-classification` (Option 1 — the keyword-rule path, not Option 2's
  LLM classification)
- `named-entity-recognition`, `velocity-spike-anomaly-detection`,
  `multi-source-triangulation`, `tfidf-semantic-clustering`,
  `vader-finance-tuned-sentiment`, `llm-sentiment-classifier-alternatives`
  (non-LLM classifier path), `structured-event-tuple-embeddings`
  (non-LLM extraction path)
- `cross-attention-gcn-news-price-fusion` (a trained neural architecture, not
  an LLM call — see its "Is it LLM-dependent?" section)
- `fincast-foundation-model`, `finmamba-graph-state-space` (time-series
  foundation models, not LLMs in the text-generation sense)

## 2. Only pre-trained models under 2–3GB

Any pre-trained model actually deployed/run in this implementation must fit
under a 2–3GB footprint. This is a deployability/cost constraint, not a
judgment on which model performs best in the research literature.

**Resolved**: "2–3GB" means actual on-disk/in-memory model footprint (not raw
parameter count) — depends on precision (fp16 vs int8 vs int4), so the same
parameter count can land on either side of the cap depending on how it's
served.

**Applying the cap against what's already been sized** (see
`../03-claude-new-methods/` "Model size / base model" sections):

| Model | Params | Footprint (fp16, ≈2 bytes/param) | Fits under 2–3GB? |
|---|---|---|---|
| BGE-M3 | ~568M | ~1.1GB | Yes |
| CKIP GPT-2 (`gpt2-base-chinese`) | 102M | ~0.2GB | Yes (also irrelevant — Chinese-only) |
| TimesFM-200M / -500M | 200M / 500M | ~0.4GB / ~1.0GB | Yes |
| Chronos-T5-small/base/large | ~8M / ~200M / ~710M | ~0.02GB / ~0.4GB / ~1.4GB | Yes |
| Kronos-mini → Kronos-large | 4M → 499M | ~0.01GB → ~1.0GB | Yes, all sizes |
| FinCast | 1B | ~2GB at fp16, ~4GB at fp32 | **Borderline** — fits at fp16, fails at fp32; confirm which precision before counting on it |
| LLaMA3-8B, LLaMA2, DeepSeek-V3 | 8B+ | 16GB+ | No |

## 3. Alpaca as the single data source

Alpaca is the single source considered for stock price data and whatever
other details Alpaca's API makes available (fundamentals, corporate
actions, etc. — whatever it actually offers) — no other price/data vendor
is in scope for this implementation phase.

Implication for the 32 `01-present-considerations` methods: all of them
assume whatever OHLCV/K-line granularity and history Alpaca can actually
provide. If a method needs a data field or resolution Alpaca doesn't
offer, that's a blocker to flag, not something to silently assume
available.

## 4. Fixed analysis time period — start date + quarterly cadence

- `start_date = 2022-01-01`, fixed — never moves.
- `end_date` is decided by calendar quarter boundary (Q1/Q2/Q3/Q4) — i.e.
  the analysis window is `[2022-01-01, Qn]`, where Qn is whichever
  quarter has just closed.
- **Significance**: `vinu-initial-analysis` runs on all tickers **4 times
  a year**, once per quarter-end, over the ever-growing
  `[2022-01-01, Qn]` window. Fixing the start date is what "maintains the
  balance" — every ticker's run stays comparable to every other ticker's
  run and to its own prior-quarter run, since they all share the same
  origin point.
- This is the concrete instantiation of **Tier 2 ("Quarterly full
  pre-analysis")** from
  `../00-project-understanding/02-storage-plan.md` — that file left the
  actual start date and the quarter-boundary semantics (question 1 in its
  "design questions" list) open; this resolves both for the
  Final-implementation phase specifically.

## Related files

- `03-actual-plan-findings/` — the actual implementation plan and project
  analysis; always check here first
- `01-present-considerations/` — where the surviving methods and full method
  details live; all forward method-discussion happens there
- `00-future-considerations/` — where the LLM-dependent, excluded methods are
  parked
- `../00-project-understanding/02-storage-plan.md` — the storage-tier
  design this file's point 4 resolves two open questions from
- `../03-claude-new-methods/00-index.md` — the method candidates this file
  filters
- `../01-news-analysis-methods/` — the L1–L4 news framework this file filters
- `../02-price-analysis-methods/` — the price-model research this file filters
