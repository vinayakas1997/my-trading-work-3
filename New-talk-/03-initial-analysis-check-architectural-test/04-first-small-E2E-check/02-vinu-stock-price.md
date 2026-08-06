---
name: e2e-check-vinu-stock-price
status: started
purpose: what to check for vinu-stock-price specifically during the first small E2E run, plus the round-wise bug/fix log for this component.
---

# vinu-stock-price — E2E Check

## What to check

- **Boot**: `stock-api` container starts cleanly with real `.env`
  values. `VINU_STOCK_DATA_ROOT=/data` required, no cwd-fallback.
- **This is the component with zero real data on disk today** (per
  `../03-actual-plan-findings/04-build-status.md`: "Zero `.parquet`
  files exist anywhere in the repo") — this check is the first time any
  of this pipeline touches real Alpaca data. Treat every step as
  unverified until proven, not "probably fine, it's tested."
- **`1min` is the only granularity actually fetched from Alpaca** — per
  `../03-actual-plan-findings/03-storage-design.md` #3. Confirm this
  directly: fetch `1min` bars for `AAPL` over a short real window, then
  request `5min`/`1hr` and confirm those come back **derived from the
  `1min` data already on disk**, not a second independent Alpaca call.
- **Daily-shard storage**: confirm the live-file layout is
  `{ticker}/{granularity}/live/{year}_{YYYYMMDD}.parquet` (today's
  shard) and `archive/{year}.parquet` (consolidated), per
  `../03-actual-plan-findings/03-storage-design.md` #4 — and per the
  correction in `../03-actual-plan-findings/04-build-status.md`'s intro
  note, this was already confirmed to exist in
  `storage/parquet.py`/`backfill/orchestrator.py` even though it wasn't
  visible from `storage/paths.py` alone. Confirm it in this real run,
  don't just trust the prior finding.
- **DB naming**: confirm `vinu_stock_price.db` (redesigned name), not
  the old `meta.db`.
- **New `/v1/stage1/vinu-stock-price/...` API**: trigger + fetch real
  `AAPL` bars through the new route, confirm the 5-field envelope.
  Confirm `granularity`/`time-range` are real positional URL segments
  now (old API used query params `interval`/`from`/`to`/`days` — per
  `../03-actual-plan-findings/04-build-status.md`, confirm the new
  route is genuinely positional, not just a thin wrapper still reading
  query params).
- **Pagination**: per
  `../03-actual-plan-findings/02-api-design.md`'s resolved item #3, page
  size is 500 records. If this check's window is `1min` granularity
  over more than 500 bars, confirm pagination actually kicks in rather
  than returning one giant unpaginated blob.

## Important things to note while running

- Alpaca rate limits: watch for 429s on real requests — note the actual
  observed limit if hit, since nothing in the docs currently states it.
- If a fetch silently returns 0 bars instead of an error (e.g. bad
  symbol, market closed, Alpaca auth failure surfaced as empty data
  rather than an explicit error) — that's a real bug to record, not
  just "no data available."
- Watch disk usage — this is the first time real Parquet files get
  written; sanity-check file sizes look reasonable for the actual bar
  count fetched (catches double-writes or duplicate-row bugs early).

## Bugs & Fixes Log

Record every real bug found and its fix here, round by round. Start a
new `BUGS-N` / `FIXES-N` pair each time this check is re-run after a
fix. Leave `(none found)` if a round is clean — don't skip the section.

### Round 1

**BUGS-1**

- Storage path deviation (finding, not a bug): the container writes 1min
  bars to `prices/1m/{SYMBOL}/live/{year}_{YYYYMMDD}.parquet` (per
  `paths.py`'s `live_year_path` + `parquet.py`'s `append_bars` day-shard
  suffix), but `plan.md`/`03-storage-design.md` #4 (as originally
  written) described `{ticker}/1min/live/{year}_{YYYYMMDD}.parquet`.
  Both are real and consistent internally (fetch works), but the on-disk
  shape differed from the plan doc.
- Container UID/permission: stock-price ran as UID 100 against host dirs
  owned by UID 1000, causing `sqlite3.OperationalError: unable to open
  database file` on the meta DB. Fixed operationally by `chmod o+rwx` on
  `data/stock-price` (no passwordless sudo); not a code fix.

**FIXES-1**

- Storage path deviation resolved by fixing the docs, not the code
  (2026-08-06): code matches its own shipped docs
  (`vinu-stock-price/README.md`, `docs/book/part-2-storage/ch08-data-layout.md`)
  and no test asserts the other path — the newer planning docs
  (`03-storage-design.md` #4, `plan.md` step 5) were describing a
  never-applied scheme. Both corrected to the real
  `prices/1m/{SYMBOL}/live/...` path.
- Permission issue fixed operationally (host chmod), not in code.
  Trigger→fetch verified: real Alpaca `1min` AAPL bars landed
  (~58k rows) and the `1hr` resample read derives from that 1min data;
  pagination works (500/page, correct next-ts continuation).
