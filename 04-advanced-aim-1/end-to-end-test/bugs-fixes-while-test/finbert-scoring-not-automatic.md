---
name: finbert-scoring-not-automatic
status: fixed-in-code
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

## Later fix (2026-08-04) — made automatic, in code, not just this run

The design question above was resolved: FinBERT scoring is now wired into
`vinu-news`'s existing background ingest loop
(`vinu-news/vinu_news/cli.py`'s `ingest_main`, the same `--continuous`
process `entrypoint.sh` already runs), not left as a standalone manual
route. Mirrors the pattern the LLM auto-analysis path already used
(`_maybe_auto_analyze`/`AutoAnalysisWorker.backfill_unanalyzed()`) rather
than inventing a new mechanism.

**What changed**, `vinu-news/vinu_news/cli.py`:
- New `run_finbert_backfill()` helper inside `ingest_main`: opens a
  `NewsService()` and loops calling `service.backfill_finbert_sentiment
(limit=500)` (the same method the manual route already called) until
  either nothing was scored in a pass or nothing remains — so it fully
  catches up in one cycle rather than trickling 500 at a time.
- Called once in the `--once`/single-shot path (after `run_rss_cycle()`/
  `run_ticker_cycle()`), and once per iteration of the `--continuous`
  loop (after the existing `sync_and_backfill()` call) — new articles get
  scored the same cycle they're ingested, same cadence as the existing
  watchlist-sync/pending-backfill catch-up already in that loop.
- `vinu-news/Dockerfile`: added `ENV PYTHONUNBUFFERED=1` — without it,
  `[finbert] scored N articles, M remaining` (a raw `logging.info`, not
  going through a handler that auto-flushes) would sit in the background
  ingest process's stdout buffer indefinitely when piped to `docker logs`,
  the same buffering gap documented in
  [`data-dir-host-uid-ownership-after-rebuild.md`](data-dir-host-uid-ownership-after-rebuild.md)'s
  sibling finding for `vinu-research`.

**A second, unrelated bug found and fixed while wiring this in**: the
existing (pre-existing, not introduced by this change) `_maybe_auto_analyze`
in `vinu-news/vinu_news/service.py:296` built one SQL `placeholders` string
sized to `watchlist` (3 tickers) and reused it for **two** different
`IN (...)` clauses in the same query — one of which needs to be sized to
`links` (the batch of newly-ingested article URLs, commonly 100+). Any
ingest cycle inserting more than 3 links crashed the entire background
ingest process with `sqlite3.ProgrammingError: Incorrect number of
bindings supplied` — which, combined with `entrypoint.sh` backgrounding
this process with `&`, meant the API server stayed `healthy` throughout
while ingestion silently stopped forever. This would have blocked the new
FinBERT automation, too, since it runs later in the same loop iteration.
Fixed: two separately-sized placeholder strings
(`link_placeholders`/`ticker_placeholders`).

**Verified against the real running stack**: rebuilt and restarted
`news-api`; the crash is gone (confirmed via `docker compose logs
news-api`, several ingest cycles completed with 100+ links each, no
traceback); manually triggered `POST /news/finbert/backfill?batch_size=500`
to confirm the underlying scoring logic still works correctly end to end
— went from `0/435` to `435/435` articles scored, confirmed via direct
`sqlite3` query against `news.db`, not the job-status endpoint alone.

**Not fully verified**: whether the *automatic* per-cycle call
(`run_finbert_backfill()` inside the `--continuous` loop, as opposed to
the manual route used above to prove the scoring logic itself) actually
fires on a live cycle — the background ingest loop hit a second, separate,
not-yet-root-caused hang inside `sync_and_backfill()` →
`service.run_backfill_all()` (see
[`news-ingest-loop-backfill-hang.md`](news-ingest-loop-backfill-hang.md)),
which sits earlier in the same loop iteration and blocks `run_finbert_
backfill()` from ever being reached on this run. The code path was
re-read carefully and the call is unconditionally reachable once
`sync_and_backfill()` returns; it just hasn't been observed firing
end-to-end inside the loop itself yet, only via the manual route above.
