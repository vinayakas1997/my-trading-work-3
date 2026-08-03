---
name: shared-watchlist-path-not-set
status: fixed
severity: silent-no-op-on-bulk-backfill-trigger
---

# Bug: `VINU_SHARED_WATCHLIST_PATH` was blank, so `vinu-news`/`vinu-stock-price` never learned the watchlist

## What was wrong

Step 1 of `02-component-triggers-and-verification.md` patches
`backfill_start_date` then calls the bulk `POST /news/backfill/trigger`
(no `ticker` param — "run all enabled/incomplete tickers at once"). Running
it produced `{"ok":true,"summary":{"job_id":"...","status":"running"}}`,
and the job immediately reported `"status":"done","results":[]` —
*empty*, not an error.

Root cause: `GET /news/watchlist/tickers` returned `{"tickers":[]}` — 
`vinu-news`'s own watchlist store was empty, even though
`data/shared/watchlist.json` had all 3 tickers. Per
[`understanding-project/b-new-ticker-added.md`](../../understanding-project/b-new-ticker-added.md),
`vinu-news` and `vinu-stock-price` are exactly the two services that keep
their **own** watchlist state, synced from the shared file only via their
own poll loop or an explicit `POST /watchlist/sync` call — never
implicitly. `run_backfill_all()` iterates *that* store, not the shared
file directly, so with 0 tickers registered it did — correctly, by its own
logic — nothing, and reported `done` because zero-tickers-processed is not
an error condition.

Attempting the sync call directly surfaced the actual root bug:
```
POST /news/watchlist/sync → {"detail":"VINU_SHARED_WATCHLIST_PATH not set"}
```
`vinu-components/.env-example`'s `VINU_SHARED_WATCHLIST_PATH=` was blank.
Both `vinu_news/config.py:68` and `vinu_stock/config.py:51` read this var
directly (`os.environ.get("VINU_SHARED_WATCHLIST_PATH", "").strip()`) with
no fallback — an empty value makes `sync_watchlist_from_shared()` a hard
no-op with an explicit error message, not a guess at a default path.

## Why it mattered

Neither `01-setup-and-rebuild.md` nor `02-component-triggers-and-verification.md`
ever calls `POST /news|stock/watchlist/sync` or checks
`GET /news|stock/watchlist/tickers` before triggering backfill. Following
the runbook exactly as written, on a fresh `.env` copied from
`.env-example`, silently backfills **zero** tickers for news and stock-price
— the single most upstream step in the whole checklist — while every
trigger call still reports success.

## What was fixed

- `vinu-components/.env-example` (and the real `.env`):
  `VINU_SHARED_WATCHLIST_PATH=/shared/watchlist.json`, with a comment
  explaining the Docker bind-mount (`./data/shared:/shared`, already present
  in `docker-compose.yml` for both `news-api` and `stock-api`) and the
  host-mode override.
- Restarted `news-api`/`stock-api` to pick up the env change, then called
  `POST /news/watchlist/sync` and `POST /stock/watchlist/sync` directly —
  both now return the 3 real tickers instead of erroring.

**Not yet fixed in the runbook itself** (flagged, not patched this pass):
`01-setup-and-rebuild.md`'s ticker-confirmation step checks
`data/shared/watchlist.json`'s contents but never confirms
`vinu-news`/`vinu-stock-price` have actually synced it into their own
stores — worth adding a `GET /news|stock/watchlist/tickers` check (and a
sync call if empty) to that file's checklist.

## What was achieved

`POST /news/backfill/trigger` (bulk, no ticker param) now actually
processes all 3 tickers instead of silently completing against zero.
