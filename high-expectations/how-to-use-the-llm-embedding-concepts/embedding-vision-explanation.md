# How to use LLM embedding concepts in VINU — vision (single-read)

Status: vision / not built — 2026-09-15
Folder: `high-expectations/how-to-use-the-llm-embedding-concepts/`
Read time: ~10 min. This one file is the whole idea.

## 0.1 Simple analogy (read this if nothing else)

Think of a doctor:

- Today VINU is like a doctor who writes a 2000-character note per patient visit (the Summary Agent summary) and then throws away the full lab report.
- The embedding idea is: keep the full lab report as numbers, filed so you can ask "show me 5 past patients with the same labs — did they recover?"
- LLM embedding = same thing for words: "show me 5 past sentences with the same meaning."

You never read 400 numbers. You read the 5 past cases they find.

## 0. TL;DR

Build a **Market Condition Embedding** for VINU, exactly like an LLM input embedding:

`all available features (~300-400 numbers) -> encoder -> one fixed-length vector per symbol+bar+timeframe -> vector store -> queryable by similarity`

Use it as **memory, not signal**: "when we saw a condition like today before, what happened next?" That 5-line answer goes into `author_trade_plan`, screener, and risk gating. It does NOT replace the Summary Agent, indicators, or LLM forecast — it makes them selective.

Re-scored significance: **6.5/10 as memory enhancer, 2/10 as standalone alpha.** Biggest value is analogue outcomes + regime gating, not direction prediction.

## 1. Important correction (read first)

An earlier note (`project-understanding/01-new-full-explanation-v2.md:106-126`) claimed `author_trade_plan` only sees 2/28 angles (`shock_*`). **That is stale and withdrawn.**

Current code proves full coverage already exists:

- `vinu-agent/vinu_agent/tools/trade_plan_tool.py:91-116` `_read_summary_context()` reads `TickerSummaryStore.get_summary(symbol)` -> `{summary, angle_digest (up to 30 angles), angles_with_data/angle_count, source_run_id}`.
- `vinu-research/vinu_research/trade_plan_authoring.py:707-743` `_normalize_summary_context()` validates + truncates to 2000 chars, fail-open to `None`.
- `vinu-research/vinu_research/forecast_skill.py:224-254` `_build_forecast_prompt()` builds: `=== Ticker Summary (X of 28 angles) ===` + narrative + `=== Angle Digest ===` + `=== Personality Features ===` (2 shock rows) + `=== Risk State ===`.

So: **summary path = 28 angles ARE in prompt. Fallback when `summary_context=None` = risk + 2-shock-only.** The vector store therefore fixes **truncation + memory**, not coverage.

## 2. LLM embedding concept in 30 seconds

In an LLM:

1. Input text -> tokens (discrete pieces).
2. **Embedding step**: each token -> dense vector via learned matrix, e.g. 768 / 1024 / 4096 dims. Similar meaning -> close vectors.
3. Vectors stored / attended over. To decode, you look up the tokenizer + output head — you never "invert" the floats by math alone.

VINU mapping is 1:1:

| LLM | VINU condition embedding |
|---|---|
| tokens | bar + all angle rows + indicators + news features for one `symbol,bar_ts,timeframe` |
| embedding matrix (learned) | encoder: v1 deterministic (concat + z-score + L2), v2 learned (PCA / autoencoder 400->64) |
| 768-dim vector | ~300-400-dim condition vector (v1), 64-dim (v2) |
| vector DB / KV-cache | parquet (truth) + ANN index (`lancedb/faiss/pgvector` — currently 0 in repo) |
| decode via tokenizer | decode via sidecar: stored `{raw_row, symbol, bar_ts, timeframe, run_ids, outcomes}` alongside vector |
| prompt + RAG | forecast prompt + 5-line neighbour block |

Mental model: **LLM embeds words to find similar meaning. We embed market conditions to find similar pasts with known outcomes.**

### Flow diagram (the whole system in 6 boxes)

```
[28 angles + indicators + news]  per symbol,bar_ts,timeframe
        |
        v
   +ENCODER v1+  select numerics -> impute -> z-score (saved mean/std) -> concat -> L2
        |
        v
[400-dim vector + sidecar row]  vector for search, raw row for human decode
        |
        v
[parquet truth + ANN index]  lancedb/faiss, keyed (timeframe, bar_ts), versioned
        |
        v
[QUERY today]  encode today -> top-k where bar_ts < today (before_ts) -> fetch outcomes
        |
        v
[USE]  5-line analogue block in forecast prompt + regime gate + screener rank
```

Encode once, read many times. Missing index = current behavior (fail-open).

## 3. What the 400-dim vector actually is

Per `symbol,bar_ts,timeframe`, concatenate curated numerics:

- 29 angles in `vinu-initial-analysis/.../storage/orchestration_registry.py:154 ANGLE_REGISTRY` x ~5-10 numerics each (~150-200 dims): `trend_lifecycle (stage/risk/confidence), regime_analysis, shock_personality (gap_fill_rate, vol_persistence, drift_days), shock_clustering, garch/kalman/arima/es forecasts + CI, chronos/moirai/timesfm/lag_llama/moment/timer/kronos quantiles, peer_relative_strength + forward_validation, news_price_causality (granger, p_value, corrs), backtesting_44_metrics (sharpe/sortino/maxDD/calmar/win_rate/var/cvar/skew/kurt), drawdown_deep_dive, session_structure`.
- `vinu-tools/vinu_tools/compute/` 24 indicators + 11 presets (~30-50 dims).
- News enrichment counts/sentiment/credibility (~20 dims).

Total lands ~250-400. That is the "embedded input" the user means. It is **not** learned on day one — it is a deterministic encoding. Learning comes later as compression.

Encoder v1 (no training, build this first):

```
select numerics -> median-impute per timeframe -> z-score with saved {mean,std,columns} per timeframe+angle-group (same pattern as vinu-research/market_regime_analogue.py:_build_feature_matrix) -> concat -> L2-normalize -> 400-dim float32
```

Encoder v2 (only after v1 proves retrieval helps): PCA or tiny autoencoder 400->64 trained walk-forward, objective = predict forward regime / return bucket. Better cosine behavior, needs versioning.

Rules that make it work (borrowed from existing `trend_lifecycle/patterns.py:build_feature_matrix/find_similar`):

- Never mix timeframes in one space (`1D` separate from `1H`/`15min`).
- Always `before_ts` filter: query at T only matches `bar_ts < T`. No future leak.
- Save `norm_params` version with every vector. Norm drift = new version, not silent overwrite.
- Cosine on normalized vectors only. Raw 400-dim Euclidean is meaningless across scales.

## 4. Is this already present, or your own theory?

Generic concept: **already present (2024-2026 research).** Your VINU fusion: **yours.**

- `FinSrag / FinSeer (arXiv 2502.05878, 2025)`: first RAG for stock movement. Core warning we must heed: generic text embeddings (`BGE, E5, Instructor, LLM-Embedder`) + DTW match surface shape, not predictive value. Domain retriever trained on financial indicators + LLM feedback beats all generics.
- `TS-RAG (2503.07649), RAFT (2505.04163), RAF (2025)`: store past contexts, retrieve top-k by embedding distance, fuse via MoE/attention. Same loop we propose, built for TSFMs like Chronos/Moirai which VINU already runs as angles.
- `Asset Embeddings (Quantitativo 2025)`: Word2Vec on holdings -> market-neutral lift. Proves latent spaces carry theme, not just stats.
- In-repo precedent: `trend_lifecycle/patterns.py` + `vinu-research/market_regime_analogue.py:253-340` (9-col z-score + cosine + `before_ts` + `build_outcome_lookup` + `get_market_regime_stats`). Proposal-only: `missing-pieces/.../reseach-explanation.md:90` suggests `Postgres+pgvector` for Hindsight, not built. FTS in `vinu-news` is lexical, not vector.

Nobody has a 28-angle deterministic VINU condition vector fusing technicals + regime + shock + news causality + peer + risk metrics per bar. That composition + outcome linkage is the own-theory part.

## 5. How usable, how much importance (corrected basis)

Not alpha alone. Memory that makes everything else selective.

| Use | Score | Comment |
|---|---|---|
| Analogue outcomes ("top-5 like today + their fwd returns") | 8/10 | Only truly new capability. Papers show consistent accuracy/Sharpe lift by avoiding bad setups. |
| Regime gate / sizing (`positive_ratio<0.4` -> skip or half-size) | 7/10 | Cheapest win once index exists; feeds `risk_gatekeeper` + `capital_allocator` directly. |
| Fix truncation loss (summary cut at 2000 chars, digest lossy) | 6/10 | Vector keeps full fidelity; LLM still reads text, retrieval is exact. |
| Screener rank across tickers | 5/10 | Needs cross-symbol norm + bigger backfill. Phase 2. |
| Predict direction standalone | 2/10 | 400-dim cosine without labels is noise. Never sell as signal. |

Expectation to set: fewer false trades, better calibration, grounded LLM reasoning. Not 2x returns. If walk-forward shows top-quartile neighbour-score plans do not beat bottom-quartile, stop before v2.

## 6. How it gets used down the line (concrete)

Assume built. Three call sites, all fail-open (missing index = current behavior).

**A. `author_trade_plan` (primary).** Encode today -> ANN top-5 with `before_ts=today` -> outcome agg. Append to `_build_forecast_prompt` after Angle Digest:

```
=== Condition Analogues (k=5, 1D, before 2026-09-15) ===
1. AAPL 2023-04-12 sim 0.91 fwd20 +3.2% maxDD -1.1% (uptrend, low vol, news-driven)
2. MSFT 2024-02-08 sim 0.88 fwd20 -2.4% maxDD -3.0% (same regime, failed breakout)
Aggregate: 3/5 positive, median fwd20 +1.8%, maxDD -2.0%
```

LLM weighs narrative as today, sizes only from Risk+Personality (keep `forecast_skill.py:162-172` rule).

**B. Risk / allocator gate.** If `n>=30, positive_ratio<0.4, median_ret<0`: Planner de-prioritizes, `risk_gatekeeper` halves size or requires extra checklist. Advisory, never hard block (same posture as `calibration.py low_trust<0.45` de-prioritize-never-gate).

**C. Screener + HypothesisRegistry.** Rank watchlist by neighbour median return, not just current signal. Log `{query_vector, decision, realized_PnL}` on close via `FeedbackLoopWorker` so calibration learns which regions you trade well.

### Worked mini-example (numbers, not theory)

Today: `RELIANCE 2026-09-15 1D` encodes to `[0.12, -0.45, ..., 0.81]` (400 numbers, L2=1.0).

Query returns (all `bar_ts < 2026-09-15`):

| # | Match | sim | fwd20 | maxDD | What it was |
|---|---|---|---|---|---|
| 1 | RELIANCE 2023-04-12 | 0.91 | +3.2% | -1.1% | uptrend, low vol, news-driven |
| 2 | RELIANCE 2024-02-08 | 0.88 | -2.4% | -3.0% | same regime, failed breakout |
| 3 | TCS 2023-11-20 | 0.86 | +2.1% | -0.8% | peer, same shock profile |
| 4 | RELIANCE 2022-06-15 | 0.84 | +0.5% | -2.2% | chop, high GARCH vol |
| 5 | INFY 2024-05-02 | 0.83 | +4.0% | -1.5% | peer momentum + Granger news |

Aggregate: `3/5 positive (excl. flat), median +2.1%, worst -3.0%` -> include as 5 lines, not 400 floats. Planner sees "looks like prior winners but one failed-breakout twin exists — require volume confirmation." That is the enhancement: same forecast call, better context.

### FAQ (the 4 confusions everyone hits)

**Q: Do we decode the vector back to numbers?**
No. Like LLM needs tokenizer, we keep sidecar `{raw_row, symbol, bar_ts, outcomes}` next to each vector. Vector finds, row explains.

**Q: Why not just put 400 numbers in the LLM prompt?**
Tokens + noise. 400 floats ≈ 2000+ tokens of low signal, and LLM reasons worse on raw floats than on "3/5 similar pasts were +2% median." Retrieve-then-summarize beats dump-everything (this is exactly the FinSeer finding).

**Q: Why not use off-the-shelf text embeddings (BGE/E5) on the summary text?**
They match wording, not market predictive value. FinSeer tested this and they lose to a domain encoder trained on indicators. Our v1 is domain by construction (z-scored market features, not English).

**Q: Does this replace Summary Agent / angles / forecast?**
No. Angles produce, summary narrates, vector remembers, forecast decides, risk gates. Remove any one and the chain breaks.

## 7. Storage (dual, minimal new infra)

- Parquet stays truth: `data/initial-analysis/...` unchanged + new `data/condition-vectors/{timeframe}/{symbol}.parquet` sidecar: `{vector float32[400], vector_version, symbol, bar_ts, timeframe, source_run_ids, forward_ret_5d/20d, forward_max_dd, regime_label}`.
- ANN index (`lancedb` recommended for local files, `faiss` alt, `pgvector` if Postgres arrives): keyed by `(timeframe, bar_ts)`, filtered by `before_ts`, versioned by `vector_version`.
- Never decode vector by math. Decode = fetch sidecar row + factsheet. Vector is for search, row is for explanation.

## 8. Build phases (stop-or-go gates)

- P0 audit (1-2 days): freeze feature list per timeframe from `spec.yaml` + `vinu-tools` catalog; define missing-data policy; pick `1D` only first.
- P1 encoder v1 (3-5 days): deterministic concat+z-score+L2 + `norm_params.json` per timeframe + backfill job reusing `run_batch` / `AngleStorage`; write sidecar parquet + `forward_ret` lookup (mirror `build_outcome_lookup`).
- P2 index + query (3-5 days): `lancedb` table + `find_similar_conditions(query, k, before_ts)` + `get_analogue_stats()`; unit-test leakage (no `>= query_ts` ever returned).
- P3 wire-in (2-3 days): optional 5-line block in `forecast_skill._build_forecast_prompt` behind flag; gate in `trade_plan_tool`; fail-open preserved.
- P4 evaluate (1 week walk-forward): do top-quartile neighbour-score plans beat bottom-quartile on forward return / win rate? If no lift, stop. If lift, consider v2 64-dim compressor.

`1H/15min` together triples backfill + norm complexity — decide after `1D` proves lift.

## 9. Risks (why naive 400-dim fails)

1. Curse of dimensionality: everything looks ~0.8 similar without per-group norm + L2. Mitigate: group z-score, optional v2 compression.
2. Leakage: one future bar in index invalidates all results. Mitigate: `before_ts` enforced in code + test, not convention.
3. Non-stationarity: 2021 low-rate pattern ≠ 2026. Mitigate: recency weight, regime-conditioned search, versioned norms.
4. Scale mismatch: `RSI 0-100` drowns `p_value 0-1`. Mitigate: z-score, never raw concat.
5. Silent drift: new angle version changes distribution. Mitigate: `vector_version` bump + re-encode, old index frozen.
6. Overconfidence: neighbours are evidence, not prediction. Mitigate: advisory only, log to calibration, never auto-promote `BENCHING->ACTIVE` on similarity alone.

## 10. Open decisions for owner

1. Scope first cut: `1D` only (recommended) vs all timeframes?
2. Store: `lancedb` local files (recommended start) vs `faiss` vs wait for Postgres+pgvector?
3. Priority use: analogue block in forecast prompt (recommended first) vs screener rank vs risk gate?
4. Budget: backfill 29 angles x watchlist x history is real compute — which symbols/time range seed v1?

---
*Supersedes the "28-vs-2 fix" framing. Coverage is done via summary+digest; this doc is about memory + fidelity behind it.*
