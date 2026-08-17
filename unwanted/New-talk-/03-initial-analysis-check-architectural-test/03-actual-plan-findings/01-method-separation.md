---
name: method-separation
status: discussion-phase
purpose: splits the 32 present-considerations methods into two sections by execution compatibility — which can run on a live article feed (in vinu-news, at ingest time) vs. which are bound to the fixed [start, Qn] windowed time-period analysis (in vinu-initial-analysis, needs price history). One file, two sections, simple.
---

# Method Separation — Time-Period + Live-Feed vs. Time-Period Only

## The split

- **Section 1 — Time-period + live-feed**: news-only methods, no price data
  needed for the core output. These can run the moment an article arrives
  (or on a short rolling window of articles) — compatible with both a live
  feed and the quarterly `[2022-01-01, Qn]` time-period analysis, since a
  per-article/per-window signal doesn't care which eventual window it gets
  aggregated into.
- **Section 2 — Time-period only**: needs price data (a historical window
  of bars, at minimum). Bound to whenever price history is available inside
  `vinu-initial-analysis`'s windowed execution — can't run purely off a live
  article stream.

## Section 1 — Time-period + live-feed analysis methods (9)

| # | Method | Why it qualifies |
|---|---|---|
| 1 | [event-type-classification](../01-present-considerations/01-event-type-classification.md) | single article, no price |
| 2 | [named-entity-recognition](../01-present-considerations/02-named-entity-recognition.md) | single article, no price |
| 3 | [velocity-spike-anomaly-detection](../01-present-considerations/03-velocity-spike-anomaly-detection.md) | article-count window, no price |
| 4 | [multi-source-triangulation](../01-present-considerations/04-multi-source-triangulation.md) | article batch, no price |
| 5 | [tfidf-semantic-clustering](../01-present-considerations/05-tfidf-semantic-clustering.md) | article batch, no price |
| 6 | [vader-finance-tuned-sentiment](../01-present-considerations/06-vader-finance-tuned-sentiment.md) | single article, no price |
| 7 | [llm-sentiment-classifier-alternatives](../01-present-considerations/07-llm-sentiment-classifier-alternatives.md) | single article, no price |
| 8 | [structured-event-tuple-embeddings](../01-present-considerations/08-structured-event-tuple-embeddings.md) | single article (extraction step), no price |
| 9 | [news-embedding-regime-detection](../01-present-considerations/32-news-embedding-regime-detection.md) | rolling news window, no price |

## Section 2 — Time-period analysis only (23)

| # | Method | Why it's time-period-bound |
|---|---|---|
| 1 | [kronos](../01-present-considerations/09-kronos.md) | needs price window |
| 2 | [chronos](../01-present-considerations/10-chronos.md) | needs price window |
| 3 | [timesfm](../01-present-considerations/11-timesfm.md) | needs price window |
| 4 | [timegpt](../01-present-considerations/12-timegpt.md) | needs price window |
| 5 | [moirai](../01-present-considerations/13-moirai.md) | needs price window(s) |
| 6 | [moment](../01-present-considerations/14-moment.md) | needs price window |
| 7 | [timer-timerxl](../01-present-considerations/15-timer-timerxl.md) | needs price window |
| 8 | [lag-llama](../01-present-considerations/16-lag-llama.md) | needs price window |
| 9 | [patchformer](../01-present-considerations/17-patchformer.md) | needs price window |
| 10 | [dlinear](../01-present-considerations/18-dlinear.md) | needs price window |
| 11 | [lstm](../01-present-considerations/19-lstm.md) | needs price window |
| 12 | [patchtst](../01-present-considerations/20-patchtst.md) | needs price window |
| 13 | [itransformer](../01-present-considerations/21-itransformer.md) | needs price window(s) |
| 14 | [tft](../01-present-considerations/22-tft.md) | needs price window |
| 15 | [lpatchtst](../01-present-considerations/23-lpatchtst.md) | needs price window |
| 16 | [tips-regime-aware-transformer](../01-present-considerations/24-tips-regime-aware-transformer.md) | needs price window |
| 17 | [arima](../01-present-considerations/25-arima.md) | needs price history |
| 18 | [garch](../01-present-considerations/26-garch.md) | needs price history |
| 19 | [kalman-filters](../01-present-considerations/27-kalman-filters.md) | needs price history (online, but still price) |
| 20 | [exponential-smoothing](../01-present-considerations/28-exponential-smoothing.md) | needs price history |
| 21 | [cross-attention-gcn-news-price-fusion](../01-present-considerations/29-cross-attention-gcn-news-price-fusion.md) | needs price window + news |
| 22 | [fincast-foundation-model](../01-present-considerations/30-fincast-foundation-model.md) | needs price window |
| 23 | [finmamba-graph-state-space](../01-present-considerations/31-finmamba-graph-state-space.md) | needs price window(s) |

## Related files

- `../01-present-considerations/00-index.md` — full detail (Input/Output
  format, LLM-dependency, model size, sources) for every method listed here
- `../limitations_and_other_info.md` — the constraints (Alpaca-only,
  2022-01-01 start, quarterly cadence) this split is planned against
