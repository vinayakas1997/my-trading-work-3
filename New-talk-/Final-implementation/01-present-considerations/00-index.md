---
name: present-considerations-index
status: discussion-phase
purpose: index of all 32 methods that survive both Final-implementation limitations (no LLM, pre-trained models under 2-3GB) — pulled from 01-news-analysis-methods (8), 02-price-analysis-methods (20, extracted from one survey file into individual files here), and 03-claude-new-methods (4). This is where all forward discussion for the phase happens, per the NOTE in ../limitations_and_other_info.md.
---

# Present Considerations — The 32 Implementable Methods

## Why this folder exists

`../limitations_and_other_info.md` sets two hard constraints for the
Final-implementation phase (no LLM implementation for now; pre-trained
models must fit under 2-3GB). Of the 39 methods/models catalogued across
this project's research, **32 survive both constraints**. This folder holds
each one as its own numbered file — `01-{method}.md` through
`32-{method}.md` — the flat, implementation-ready view of everything
eligible right now.

The 7 that don't survive live in `../00-future-considerations/` instead —
parked, not discarded.

## Where these came from

- **01–08**: the 8 news-analysis methods, originally in
  `../../01-news-analysis-methods/pure-keyword-methods/` (still there too —
  that folder is the permanent research archive; these are working copies
  for this phase).
- **09–28**: 20 price-only models, extracted from the single survey file
  `../../02-price-analysis-methods/price-analysis-methods.md` into
  individual files for the first time. Detail depth varies — Kronos,
  iTransformer, TIPS, and the 6-model comparison table had real
  substance in the source; TimeGPT/MOIRAI/MOMENT/Timer-XL are thinner
  (named but not deep-dived in the original research pass) — flagged
  honestly in each file rather than padded out.
- **29–32**: the 4 survivors from `../../03-claude-new-methods/` (that
  folder is now fully resolved/historical — see its index).

## Index

### News-analysis methods (01–08) — all LLM-free paths, all trivially under the size cap

1. [`01-event-type-classification.md`](01-event-type-classification.md) — keyword-rule event sub-types (Option 1 only)
2. [`02-named-entity-recognition.md`](02-named-entity-recognition.md) — regex/dictionary entity extraction
3. [`03-velocity-spike-anomaly-detection.md`](03-velocity-spike-anomaly-detection.md) — news-volume z-score anomaly
4. [`04-multi-source-triangulation.md`](04-multi-source-triangulation.md) — same-story multi-source confirmation
5. [`05-tfidf-semantic-clustering.md`](05-tfidf-semantic-clustering.md) — TF-IDF headline clustering
6. [`06-vader-finance-tuned-sentiment.md`](06-vader-finance-tuned-sentiment.md) — VADER + finance lexicon (not recommended — same disproven-signal family)
7. [`07-llm-sentiment-classifier-alternatives.md`](07-llm-sentiment-classifier-alternatives.md) — DeBERTa/RoBERTa classifiers (not recommended — same reason)
8. [`08-structured-event-tuple-embeddings.md`](08-structured-event-tuple-embeddings.md) — event-tuple embeddings (SRL path only, not the LLM path)

### Price-only foundation models (09–17) — the Kronos/TSFM family

9. [`09-kronos.md`](09-kronos.md) — the flagship, 4M–499M params
10. [`10-chronos.md`](10-chronos.md) — Amazon, 8M–710M params
11. [`11-timesfm.md`](11-timesfm.md) — Google, 200M/500M params
12. [`12-timegpt.md`](12-timegpt.md) — size unconfirmed
13. [`13-moirai.md`](13-moirai.md) — any-variate attention, size unconfirmed
14. [`14-moment.md`](14-moment.md) — size unconfirmed
15. [`15-timer-timerxl.md`](15-timer-timerxl.md) — size unconfirmed
16. [`16-lag-llama.md`](16-lag-llama.md) — LLaMA-architecture, probabilistic output, size unconfirmed
17. [`17-patchformer.md`](17-patchformer.md) — size unconfirmed

### Trained-from-scratch price architectures (18–23) — the ones that actually win on finance

18. [`18-dlinear.md`](18-dlinear.md) — ~50% dir. acc., linear baseline
19. [`19-lstm.md`](19-lstm.md) — ~51% dir. acc.
20. [`20-patchtst.md`](20-patchtst.md) — ~50% dir. acc., regularizing
21. [`21-itransformer.md`](21-itransformer.md) — ~50% dir. acc., cross-asset
22. [`22-tft.md`](22-tft.md) — ~53% dir. acc., top performer
23. [`23-lpatchtst.md`](23-lpatchtst.md) — ~54% dir. acc., **best performer**, Sharpe 2.31–2.32

### Regime-aware and classical (24–28)

24. [`24-tips-regime-aware-transformer.md`](24-tips-regime-aware-transformer.md) — regime-adaptive transformer
25. [`25-arima.md`](25-arima.md) — classical baseline
26. [`26-garch.md`](26-garch.md) — classical, volatility-specific
27. [`27-kalman-filters.md`](27-kalman-filters.md) — classical, state estimation
28. [`28-exponential-smoothing.md`](28-exponential-smoothing.md) — classical baseline

### New architectures from the Aug 2026 web-search pass (29–32)

29. [`29-cross-attention-gcn-news-price-fusion.md`](29-cross-attention-gcn-news-price-fusion.md) — multi-stock news+price fusion, 7.11% MAE reduction
30. [`30-fincast-foundation-model.md`](30-fincast-foundation-model.md) — 1B params, **borderline** on the size cap (fp16 passes, fp32 fails)
31. [`31-finmamba-graph-state-space.md`](31-finmamba-graph-state-space.md) — Mamba/SSM architecture, size unconfirmed
32. [`32-news-embedding-regime-detection.md`](32-news-embedding-regime-detection.md) — news→regime, no confirmed source paper

## Reading this list honestly

Not all 32 are equally ready. A rough tiering:

- **Well-documented, low-risk, cheap to test now**: 01–08 (all keyword/
  classical, zero training needed except #8), 09 (Kronos), 21–23
  (iTransformer/TFT/LPatchTST), 25–28 (classical).
- **Documented but size/precision needs confirming**: 30 (FinCast).
- **Named but thin — need a dedicated read before deciding anything**:
  12–17 (TimeGPT, MOIRAI, MOMENT, Timer-XL, Lag-Llama, PatchFormer), 31
  (FinMamba's exact size).
- **No confirmed source at all**: 32 (news-embedding regime detection) —
  treat as an idea to validate exists in the literature, not a method to
  implement yet.

## Related files

- `../limitations_and_other_info.md` — the two constraints that produced
  this list
- `../00-future-considerations/00-index.md` — the 7 that didn't survive
- `../../01-news-analysis-methods/` — original source for files 01–08
- `../../02-price-analysis-methods/price-analysis-methods.md` — original
  source for files 09–28
- `../../03-claude-new-methods/00-index.md` — original source for files
  29–32 (now resolved/historical)
