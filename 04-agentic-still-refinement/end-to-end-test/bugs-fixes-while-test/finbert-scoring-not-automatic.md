---
name: finbert-scoring-not-automatic
status: fixed-in-this-run-not-in-code
severity: silently-missing-signal-for-significance_score
---

# Gap: FinBERT sentiment scoring never runs automatically — needs a separate manual trigger the runbook never mentions

## What was wrong

`vinu-news` has two independent sentiment pipelines: the qwen LLM's
`analyze_article()` (auto-triggered per article when
`llm_analysis_mode: auto`, confirmed active — `article count` climbed
during backfill exactly as expected) and a completely separate FinBERT
model (`vinu_news/analysis/enrichment/finbert_sentiment.py`,
`ProsusAI/finbert`, baked into the image at `/app/models/finbert` so no
network/cache is needed at runtime).

FinBERT scoring is **only** reachable via
`POST /news/finbert/backfill?batch_size=500` (`routes_config.py:292`) — a
separate, manual, batched job. Nothing in the ingestion cycle, the
auto-analysis worker, or the backfill trigger ever calls it. Confirmed by
reading `service.py`'s `backfill_finbert_sentiment()` (line 738) — it's
defined but has no caller anywhere except that one route.

This matters beyond "an unused feature": `vinu-initial-analysis`'s
`significance_model.py` reads `finbert_score` as an input feature for
`significance_score`. Without ever triggering this route, every symbol's
significance classification would run against `NULL` FinBERT scores for
every article — a silent degradation of exactly the kind this whole
project's testing discipline exists to catch, since nothing about it
errors or shows up as missing in any of `02`'s or `03`'s verification
steps.

`02-component-triggers-and-verification.md`'s `vinu-news` section never
mentions this route at all.

## Why it mattered

Same shape as the watchlist-sync gap: a real, working feature that the
runbook simply never calls, with no error to signal it's missing — the
initial-analysis angles would compute and report `completed` normally,
just off partially-blind input.

## What was done this run

Triggered manually: `POST /news/finbert/backfill?batch_size=500`, twice
(once before, once after a `news-api` restart wiped the first job's
in-memory tracking — the actual scoring work itself is persisted to
`/data/news.db` and survived the restart). Confirmed via direct query:
21,016 of 21,018 articles scored with `finbert_score` by the end of this
pass.

## Not fixed this pass — flag for follow-up

- `02-component-triggers-and-verification.md`'s `vinu-news` section should
  add this route as an explicit trigger-and-verify step (verify:
  `SELECT COUNT(*) FROM articles WHERE finbert_score IS NULL` trends to 0),
  the same way the news/stock backfill steps are documented.
- Whether this should instead become part of the automatic ingestion path
  (score on ingest, not as a separate backfill sweep) is a real design
  question, not decided or changed here — this file only documents the
  current, confirmed-manual behavior and gets the data populated for this
  specific run.
