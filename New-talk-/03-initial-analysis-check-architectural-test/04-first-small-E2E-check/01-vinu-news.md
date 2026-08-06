---
name: e2e-check-vinu-news
status: started
purpose: what to check for vinu-news specifically during the first small E2E run, plus the round-wise bug/fix log for this component.
---

# vinu-news — E2E Check

## What to check

- **Boot**: `news-api` container starts cleanly with real `.env` values.
  `VINU_NEWS_DATA_ROOT=/data` is required (no cwd-fallback per
  `../03-actual-plan-findings/03-storage-design.md` #1) — confirm it
  actually fails loudly if unset, rather than silently falling back.
- **DB naming**: confirm the live DB file is `vinu_news.db` (the
  redesigned name), not the old `news.db`/`meta.db`.
- **Alpaca fetch**: trigger real news ingest for `AAPL` over a short
  recent window. Confirm articles actually land in the DB (row count
  check), not just a 200 response with an empty result.
- **LLM env vars — important edge case**: `.env-example` includes
  `VINU_LLM_*` variables shared by vinu-news (for whatever still uses an
  LLM path). Per `../limitations_and_other_info.md` #1, **no LLM
  implementation is in scope for this phase**. Confirm the 9 Section-1
  methods (`event-type-classification`, `named-entity-recognition`,
  `velocity-spike-anomaly-detection`, `multi-source-triangulation`,
  `tfidf-semantic-clustering`, `vader-finance-tuned-sentiment`,
  `llm-sentiment-classifier-alternatives` non-LLM path,
  `structured-event-tuple-embeddings` non-LLM path,
  `news-embedding-regime-detection`) all work correctly with
  `VINU_LLM_*` left blank / no local LLM server running. If any of them
  silently depend on the LLM endpoint being up, that's a real finding —
  record it.
- **FinBERT**: confirm it loads from the shared `data/models/finbert`
  dir mounted at `/models` (not baked into the image — the bake step was
  removed per `../03-actual-plan-findings/06-models-download.md`), and
  actually scores real ingested articles (`model_backend` should reflect
  a genuine load, not silently falling back).
- **New `/v1/stage1/vinu-news/...` API**: trigger + fetch at least one
  Section-1 method against the real ingested articles from this run.
  Confirm the 5-field response envelope (`run_id`, `status`,
  `computed_at`, `tier`, `data`) is actually correct, not just present.
- **Live-feed time-range shape**: per
  `../03-actual-plan-findings/02-api-design.md`, a live-feed call is
  just a very recent `{start-time}_{end-time}` window with full
  timestamp precision. Confirm this actually works against real just-
  ingested articles (e.g. last 15 minutes), not only against the
  quarterly-style window.

## Important things to note while running

- Watch for the cwd-fallback bug being silently reintroduced — if the
  container starts without `VINU_NEWS_DATA_ROOT` set and doesn't crash,
  that's a regression against the redesign.
- The job-state dict for `/ingest/trigger`/`/backfill/trigger` was
  previously in-memory, capped at 50, not persisted (per
  `../03-actual-plan-findings/04-build-status.md`). Watch whether the
  new `/v1/stage1/.../trigger` path has the same limitation or a real
  fix — note whichever it is.

## Bugs & Fixes Log

Record every real bug found and its fix here, round by round. Start a
new `BUGS-N` / `FIXES-N` pair each time this check is re-run after a
fix. Leave `(none found)` if a round is clean — don't skip the section.

### Round 1

**BUGS-1**

- LLM worker would not stop via `PATCH /news/settings` `auto→manual`:
  the settings endpoint writes `.env` (env) but the service reads the
  `vinu_settings` DB row first (`service.py` ~277-279), so the env
  change alone was overridden by the DB value. Restarted the container
  and verified 0 new LLM calls; DB + env both now `manual`.
- `shutdown()` is non-blocking by design — it stops new dispatches and
  drains the in-flight queue rather than killing workers. Confirmed
  behavior, not a crash; article_count held at 16180 after stop.
- Job-state trim: the in-memory `_jobs` map trims to 50 entries. Same
  documented limitation carried into the v1 path — confirmed present,
  not a regression.

**FIXES-1**

- Set `llm_analysis_mode` to `manual` in both the DB `vinu_settings`
  row and the `.env` (env is a fallback behind the DB). Verified by
  restarting the container and confirming 0 new LLM calls over the
  follow-up window; `GET /news/settings` shows `manual`.
