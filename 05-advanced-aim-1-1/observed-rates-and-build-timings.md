---
name: observed-rates-and-build-timings
status: measured-2026-08-04
purpose: real, measured numbers from running the telemetry layer and the FinBERT-automation fix against the live Docker stack on 2026-08-04 — LLM call latency/throughput (vinu-research and vinu-news separately, since they're very different workloads), FinBERT scoring throughput, and per-service Docker build timings (fresh vs. cached). Every number here came from a direct query against telemetry.db, news.db, or a timed `docker compose build` — none are estimates. Companion to status.md/end-to-end-test.md; this file is the numbers, not the design.
---

# Observed Rates and Build Timings — 2026-08-04

## Why this file exists

`AGENTS.md`/`status.md` describe what the telemetry layer and the FinBERT
automation fix (`04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/
finbert-scoring-not-automatic.md`) do. This file is the other half: what
actually happened when they ran against the real stack, in real numbers —
so the next agent doesn't have to re-run and re-measure any of this from
scratch to know what to expect.

## LLM call latency — `vinu-research` (strategy generation/critic calls)

Source: `sqlite3` query against `vinu-components/data/research/
telemetry.db`'s `llm_calls` table, 13 real calls made triggering one
`POST /research/run` for AAPL with `VINU_RESEARCH_LLM_ENABLED=true`
(model: `qwen36-35B`, via `vinu-lib`'s `LlmClient`).

| Metric | Value |
|---|---|
| Calls | 13 |
| Latency — min | 1.70s |
| Latency — avg | 114.27s |
| Latency — max | 349.73s |
| Total retries (sum of `retry_count`) | 6 |
| `parse_error` outcomes | 3 of 13 |

The three `parse_error` calls each still cost **107–113 seconds** of
latency with zero tokens returned — the model was queried, took a long
time, and returned something `vinu-research`'s response parser rejected.
That's real wasted wall-clock time this telemetry layer now makes visible
(`token_count_source`/`outcome` columns), where before it would only have
shown up as "the research run took a while," with no way to tell how much
of that was retries or wasted parse failures without re-reading raw logs.

Per-call detail (real rows, not averaged):

| ts | prompt_tokens | completion_tokens | retry_count | latency_sec | outcome |
|---|---|---|---|---|---|
| 07:31:37 | 383 | 137 | 0 | 9.05 | completed |
| 07:31:46 | 213 | 112 | 0 | 7.65 | completed |
| 07:32:04 | 422 | 295 | 0 | 18.80 | completed |
| 07:37:39 | 1080 | 1282 | 2 | 334.66 | completed |
| 07:37:48 | 1080 | 1585 | 2 | 343.86 | completed |
| 07:37:54 | 1080 | 1954 | 2 | 349.73 | completed |
| 07:39:41 | 0 | 0 | 0 | 106.93 | parse_error |
| 07:41:34 | 0 | 0 | 0 | 112.66 | parse_error |
| 07:43:27 | 0 | 0 | 0 | 112.93 | parse_error |
| 07:43:57 | 1497 | 1935 | 0 | 30.27 | completed |
| 07:44:32 | 1518 | 2180 | 0 | 35.24 | completed |
| 07:44:54 | 1518 | 1471 | 0 | 22.02 | completed |
| 07:44:56 | 374 | 97 | 0 | 1.70 | completed |

Note the three calls at 07:37:39–07:37:54 all show `retry_count: 2` and
5–6-minute latency each — a real, visible cost of the retry path this
session's `agent/llm.py` rewrite made observable
(`05-advanced-aim-1-1/status.md` §3). Effective completion-token
throughput varies enormously by call: the 349.73s/1954-token call is
**~5.6 tokens/sec**, the 1.70s/97-token call is **~57 tokens/sec** — short
calls pay much less fixed overhead per token than long ones against this
local `qwen36-35B` endpoint.

## LLM call rate — `vinu-news` (per-article auto-analysis)

Source: two live samples of `SELECT COUNT(*) FROM news_analysis`
144 seconds apart, isolated to AAPL articles, while the background
`vinu-news-ingest --continuous` process was actively working through a
real backlog (concurrency=3, per `VINU_LLM_ANALYSIS_CONCURRENCY=3` in
`.env`).

- **679 → 707 analyzed in 144s → ~11.7 articles/min** (measured, not
  estimated).
- This is a much shorter per-call prompt than `vinu-research`'s strategy
  critic (article headline/summary vs. full backtest metrics + market
  story blocks), so its latency profile is not comparable to the table
  above — no direct latency numbers were captured for this path this
  pass, only aggregate throughput.
- At this rate, a backlog of ~7,228 AAPL articles needing analysis would
  take **~9.3 hours** to fully clear — this is the slow path in the
  pipeline right now, not FinBERT (below).

## FinBERT scoring throughput

Source: `vinu-news/vinu_news/analysis/enrichment/finbert_sentiment.py`'s
`score_finbert_batch` (`ProsusAI/finbert`, baked into the image,
`batch_size=16` sub-batches, `torch.set_num_threads(1)`, running in the
now-independent `vinu-news-finbert` process — see
[`../04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/finbert-scoring-not-automatic.md`](../04-advanced-aim-1/end-to-end-test/bugs-fixes-while-test/finbert-scoring-not-automatic.md)).

- **One full `backfill_finbert_sentiment(limit=500)` batch: 500 articles
  scored in 133 seconds → ~3.8 articles/sec ≈ 226 articles/min.**
- Progress is only visible externally in 500-article jumps — the whole
  batch is scored in memory (32 sub-batches of 16 through the BERT model)
  before one `conn.executemany()` + `commit()` writes all 500 rows at
  once. Watching the DB between commits looks identical to a hang (zero
  movement for ~2 minutes), confirmed via `py-spy dump` to actually be
  mid-computation, not stuck — see the bug file above for the full
  investigation. **If instrumenting or monitoring this again, sample on a
  timescale of minutes, not seconds, or the batch-commit granularity will
  read as a false stall.**
- At ~226/min, the full 16,063-article backlog (all 3 tickers combined)
  clears in **~71 minutes** — an order of magnitude faster than LLM
  analysis, once decoupled from waiting behind it (before the fix in the
  bug file above, FinBERT was blocked indefinitely behind
  `AutoAnalysisWorker.shutdown()`'s `queue.join()`).

## Docker build timings — per service, 2026-08-04

All measured with `time docker compose build <service>`, one at a time,
after adding `py-spy` to every Dockerfile
(`RUN pip install --no-cache-dir py-spy`, placed immediately before each
`USER app` line) and `SYS_PTRACE` to every service's `cap_add` in
`docker-compose.yml`.

| Service | Build time | Notes |
|---|---|---|
| `news-api` | 6.8s | fully cached (first pass) |
| `research-api` | 0.66s | fully cached |
| `agent-api` | 6.1s | fully cached |
| `initial-analysis-api` | **8m24.6s (504.4s)** | **not cached** — dominated by `RUN pip install --no-cache-dir -e "/app/vinu-tools[ml]"` alone taking **458.7s**; every other layer was cache-hit or under 1s |
| `live-api` | 1.75s | fully cached |
| `portfolio-api` | 0.5s | fully cached |
| `simulator-api` | 0.5s | fully cached |
| `stock-api` | 0.6s | fully cached |
| `strategy-api` | 0.5s | fully cached |
| `features-api` | 0.6s | fully cached |
| `news-api` (2nd rebuild, after the FinBERT-decoupling code change to `service.py`/`cli.py`) | 2m4.4s (124.4s) | source-code layer changed, invalidating everything from `COPY vinu-news` onward, including a fresh (non-cached) `py-spy` download this time (3.9s of the 124.4s) |

**Why `initial-analysis-api` was the outlier**: `vinu-tools[ml]` pulls in
heavier ML dependencies (the `[ml]` extra) than any other service's
`pip install -e .` step, and this particular layer wasn't cache-hit on
this build (BuildKit cache eviction or a base-layer digest change —not
investigated further, since it's a pre-existing dependency-install cost
unrelated to anything changed this session, not something `py-spy`'s
addition caused). Every other service's `py-spy` layer added under 10
seconds when actually uncached, confirmed by the second `news-api` build
above (3.9s for a fresh `py-spy` download).

## What this means in practice for the next agent running `05`'s runbook

- A full `docker compose down && up --build -d` after a code change should
  normally take low single-digit minutes across all 10 services combined,
  **unless** `initial-analysis-api`'s `vinu-tools[ml]` layer cache has been
  evicted, in which case budget an extra ~8 minutes for that one service
  alone — don't assume something is broken if one service's build takes
  disproportionately longer than the other nine.
- When checking FinBERT or any other batch-commit-style background job for
  progress, poll on a **multi-minute** cadence, not seconds — sub-batch
  computation is invisible externally by design (see above), and a short
  polling window will produce a false "it's stuck" reading.
- `vinu-research`'s real per-call LLM latency (avg 114s, max 350s in this
  sample) means a `POST /research/run` triggering several LLM calls
  (critic + summarize) can legitimately take many minutes end to end —
  budget accordingly when scripting or timing out any future runbook step
  that calls this route.
