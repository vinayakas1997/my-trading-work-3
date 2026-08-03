---
name: e2e-component-triggers
status: definition-phase
---

# Step 2 — Per-Component Trigger and Verification Checklist

## How to use this file

One section per service, in the same dependency order `docker-compose.yml`
enforces (`depends_on`). Each section has exactly three parts:

- **Trigger** — the exact command/route to run for this ticker set and
  date range.
- **Verify** — the exact read-route or file to check afterward. A 200
  response from the trigger call is not verification; check the data
  actually landed.
- **Document** — what to write down before moving to the next service (so
  the next person/session doesn't have to re-derive it).

Do these in order. `vinu-strategy`/`vinu-research`/`vinu-simulator` are
covered in `03-strategy-research-and-simulation.md`, not here.

---

## 1. `vinu-news` (port 8080)

### Trigger

News backfill range is controlled by a **setting**, not a per-call
parameter — default is `2023-01-01`, which is later than this run's start
date, so it must be patched first:

```bash
curl -X PATCH http://localhost:8080/news/settings \
  -H "Content-Type: application/json" \
  -d '{"backfill_start_date": "2022-01-01"}'
```

Then trigger backfill for all three tickers (omit `ticker` query param to
run all enabled/incomplete tickers at once):

```bash
curl -X POST http://localhost:8080/news/backfill/trigger
```

Or per-ticker, if you want to isolate failures:

```bash
curl -X POST "http://localhost:8080/news/backfill/trigger?ticker=AAPL"
curl -X POST "http://localhost:8080/news/backfill/trigger?ticker=TSLA"
curl -X POST "http://localhost:8080/news/backfill/trigger?ticker=JNJ"
```

This returns a `job_id` — it's async, not synchronous.

### Verify

```bash
curl -s http://localhost:8080/news/backfill/status
curl -s "http://localhost:8080/news/backfill/job/{job_id}"
```

Confirm each job's status is `completed` (not `running`/`failed`), and that
the reported date range actually starts at/near `2022-01-01`, not
`2023-01-01` (the default) — that would mean the settings patch didn't
take effect before the trigger ran.

### On re-run

Per-ticker backfill state is persisted (`backfilled_up_to_ts` in
`vinu_news/backfill/store.py`) and resumed incrementally, not
re-fetched — confirmed via `service.py:442-468`:

- `run_backfill_all()` (the bare `POST /news/backfill/trigger`) **skips
  any ticker whose status is already `completed` entirely** — a second
  full-range trigger against an already-backfilled watchlist is a no-op,
  not a re-verify.
- `run_backfill_single(ticker)` only reads the `backfill_start_date`
  setting for a ticker with **no existing status row**. Once a status row
  exists (from a prior run, even a partial/failed one), the setting patch
  in step 1 above has **no effect** on it — it resumes from
  `backfilled_up_to_ts`, ignoring the setting.
- There is no exposed route to reset a ticker's backfill status. If a
  ticker's coverage needs to start earlier than whatever it already has,
  the only path is directly clearing its row in the backfill-status table
  — this file doesn't do that, so if this checklist is being re-run
  against a stack that already has partial AAPL/TSLA/JNJ coverage from an
  earlier attempt, the `backfill_start_date` patch in step 1 will silently
  not take effect for those tickers. Check `/news/backfill/status` for an
  existing (non-empty) status row *before* patching the setting and
  assuming it will apply.

### Document

- Job IDs and final status for each of the 3 tickers.
- The actual earliest article date returned per ticker (may not be exactly
  2022-01-01 if the underlying news source has no coverage that far back —
  note the real earliest date, don't assume the setting guarantees it).

---

## 2. `vinu-stock-price` (port 8081)

### Trigger

Backfill is year-granular (`from_year`/`to_year`), hard-floors at 2022
(`backfill/orchestrator.py:25`, `MIN_BACKFILL_YEAR = 2022`), and — this is
the part easy to get wrong — **`end_year` defaults to `current_year - 1`
when not given, and the HTTP route never exposes a `to_year`/`end_year`
field at all** (`BackfillRequest` in `server/routes_config.py:98-100` only
has `symbols`/`force`). `force: true` only forces `from_year=2022`; it does
**not** affect the end of the range. This means the call below, on its
own, will only backfill through **2025**, not 2026-06-30, no matter what
flag is set:

```bash
curl -X POST http://localhost:8081/stock/backfill/trigger \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL", "TSLA", "JNJ"], "force": true}'
```

**A second call is required** to actually reach 2026-06-30 — the live-ingest
cycle (`run_live_cycle`, `live/ingest_cycle.py:95`) resumes each symbol from
its `last_bar_ts` (the end of whatever backfill just wrote, i.e. end of
2025) forward to "now" — since "now" during this checklist is genuinely
past 2026-06-30, one call after backfill completes bridges the gap:

```bash
curl -X POST http://localhost:8081/stock/ingest/trigger
```

Run this only after the backfill job above shows `completed` for all 3
symbols — `run_live_cycle` reads each symbol's `last_bar_ts` from the
catalog, so if it runs first there's nothing to resume from yet.

### Verify

```bash
curl -s "http://localhost:8081/stock/backfill/status/{job_id}"
curl -s "http://localhost:8081/stock/ingest/status/{job_id}"  # same job-status shape, from the ingest trigger's job_id
```

Confirm `completed` status for all 3 symbols on **both** jobs. Then
spot-check actual candle coverage directly (not just job status) for each
symbol at both ends of the range — e.g. a `get_candles`-style read call for
early January 2022 and late June 2026 — to confirm data exists at the
boundaries, not just somewhere in the middle. The late-June-2026 boundary
check is the one that actually exercises the ingest-trigger call above —
don't skip it, it's the only thing that would catch this gap recurring.

### Document

- Job IDs and completion status per symbol, **for both the backfill job
  and the ingest-trigger job** — a completed backfill job alone does not
  mean 2026 coverage exists.
- Confirmed candle coverage at both range boundaries (2022-01 and 2026-06)
  for all 3 symbols — this is the single most important verification in
  this whole file, since every downstream service depends on this data
  existing for the full range, and it's the only check that actually
  proves the ingest-trigger call landed real 2026 data rather than just
  returning `completed` on an empty poll.

---

## 3. `vinu-tools` / features (port 8082)

### Trigger

```bash
curl -X POST http://localhost:8082/features/requests \
  -H "Content-Type: application/json" \
  -d '{
    "title": "e2e-backfill-AAPL",
    "symbols": ["AAPL"],
    "from_ts": 1640995200,
    "to_ts": 1782777600,
    "preset": "trend_pack",
    "run_immediately": true
  }'
```

(`from_ts`/`to_ts` above are 2022-01-01 and 2026-06-30 as Unix epoch
seconds — recompute exactly rather than trusting these if this file is
reused later.) Repeat for TSLA and JNJ (one request per symbol; the schema
accepts a `symbols` list but confirm whether multi-symbol requests are
actually processed per-symbol or as one combined run before assuming
either).

### Verify

```bash
curl -s "http://localhost:8082/features/requests/{request_id}"
curl -s "http://localhost:8082/features/requests/{request_id}/data"
```

Confirm `status: completed` and that `/data` actually returns rows spanning
the requested range, not an empty result.

### On re-run

`service.py:124-127` hashes the full request (`symbols`, `from_ts`,
`to_ts`, `preset`/`features`) and returns the existing `DONE` request
unchanged if an identical hash already completed — a byte-identical
re-trigger of this exact call is a genuine, cheap no-op (same
`request_id` comes back, nothing recomputes). Changing anything in the
payload (even just `title`) does **not** change the hash — `title` isn't
part of `_hash_request`'s inputs — so don't assume a different `title`
forces a fresh run.

### Document

- Request IDs per symbol and final status.
- Row count returned per symbol — a suspiciously low count (e.g. far fewer
  than ~4.5 years of daily bars would imply) is worth flagging before
  moving on, not silently accepted.

---

## 4. `vinu-initial-analysis` (port 8083)

### Trigger

No bulk/multi-symbol route exists — one call per ticker. No batching
inside the service either (`AngleRunner.run`, `runner.py:81-108` passes the
full `from_ts..to_ts` straight to each angle's `compute()` in one shot), so
this is one large in-process computation per ticker, not several smaller
calls:

```bash
curl -X POST "http://localhost:8083/analysis/run/AAPL?from_ts=1640995200&to_ts=1782777600"
curl -X POST "http://localhost:8083/analysis/run/TSLA?from_ts=1640995200&to_ts=1782777600"
curl -X POST "http://localhost:8083/analysis/run/JNJ?from_ts=1640995200&to_ts=1782777600"
```

Omit `angle_names` to run every registered angle (recommended for this
run — the point is full coverage, not a subset). This may take a while per
symbol given the range size; don't assume a fast response.

### Verify

```bash
curl -s http://localhost:8083/analysis/symbols
curl -s http://localhost:8083/analysis/angles
curl -s http://localhost:8083/analysis/angle/regime_analysis/AAPL
```

Confirm all 3 symbols appear in `/analysis/symbols`, and that
`/analysis/angle/regime_analysis/{ticker}` returns real rows with
`analysis_at` timestamps — this is also the exact route
`vinu_agent/audit/freshness.py`'s `FreshnessChecker` reads from, so
confirming it here directly de-risks that piece too.

### Document

- Per-symbol: which angles ran, row counts, and whether any returned
  `status: "no_data"` or `"insufficient_data"` (both are real statuses this
  service returns when a symbol's data is too thin — worth knowing before
  assuming every angle produced usable output).
- The dedupe guard (`RunLog.has_existing_run`) means re-running this same
  call a second time will skip, not recompute — note whether this was a
  fresh run or a skip, since a skip against stale data would silently look
  identical to a fresh, correct one.

---

## 5. `vinu-portfolio` and `vinu-live`

Neither needs a historical backfill trigger of its own — both are
downstream, derived services that read from strategy/research/simulator
output and from the live broker respectively. Confirm they're healthy
(`docker compose ps`) and skip any further action here; their actual use
comes in `03` (portfolio, indirectly, via strategy artifacts) and in the
`vinu-agent` session at the end of this folder's checklist (live, only if
running the live-mode agent step, not the historical backfill).

## What to confirm before moving on to `03`

- [ ] News backfill completed for all 3 tickers, earliest article date
      documented (may be later than 2022-01-01 — that's a real finding,
      not a failure, if the underlying source has no earlier coverage)
- [ ] Stock-price: both the backfill trigger **and** the ingest trigger
      run (backfill alone only reaches 2025), candle coverage confirmed
      at both range boundaries (2022-01 and 2026-06) for all 3 tickers
- [ ] Feature requests completed for all 3 tickers with non-trivial row
      counts
- [ ] Initial-analysis ran (not skipped-as-duplicate against stale/empty
      data) for all 3 tickers, all angles, with real row counts and
      `analysis_at` timestamps confirmed via the same route the freshness
      reader uses
