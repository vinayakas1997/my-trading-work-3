---
name: news-ingest-loop-backfill-hang
status: mitigated-not-root-caused
severity: silently-stops-all-news-ingestion-and-backfill-indefinitely
---

# Bug: `vinu-news`'s background ingest loop hangs indefinitely inside `run_backfill_all()`, with zero log evidence of where — mitigated by restart, not root-caused

## What was wrong

While verifying the FinBERT automation fix
([`finbert-scoring-not-automatic.md`](finbert-scoring-not-automatic.md))
against the real running stack on 2026-08-04, `news-api`'s background
ingest loop (`vinu-news-ingest --continuous`, started by `entrypoint.sh`)
stopped making any forward progress roughly one cycle after the container
started, and stayed stuck for 90+ minutes with **zero** CPU usage
(`docker stats`: `0.12%`) and zero new log lines beyond the first RSS/
ticker cycle's summary report.

Confirmed via `GET /news/backfill/status`: `AAPL`'s `updated_at` field
never changed across the entire observation window, and cross-checking
that timestamp against wall-clock time showed it predated this session's
`news-api` rebuild entirely — meaning `run_backfill_all()` (called from
`sync_and_backfill()`, itself called once per loop iteration) had not
completed even a single iteration since the container started. No
`Chunk [...] permanently failed` or `Providers failed` log line appeared
either (both are logged on any provider error inside
`run_backfill_single()`'s per-chunk loop), which rules out a slow-but-
progressing failure-and-retry pattern — the process appears to be blocked
before ever reaching (or inside) the very first network call of the
backfill loop, silently, with no exception, no partial progress logged,
and no CPU consumed.

## What was ruled out, with evidence, not assumption

- **Not a code-level crash**: no traceback in `docker compose logs
  news-api` for the entire stuck window.
- **Not the alpaca provider's HTTP timeout misbehaving**:
  `vinu-news/vinu_news/providers/alpaca.py:14` sets `TIMEOUT_SEC = 30`,
  passed through to `requests.request(..., timeout=TIMEOUT_SEC)` in
  `vinu-news/vinu_news/net.py` — a single call should not be able to hang
  past ~30s (or a few multiples of it, across `net.request`'s own
  3-attempt retry loop), nowhere near 90 minutes.
- **Not the shared watchlist file lock**: `vinu-news/vinu_news/watchlist/
  shared.py` uses `filelock.FileLock` with no explicit timeout around
  `read_shared`/`write_shared`, which was a real candidate (an
  un-timeout'd lock blocking forever on real contention, or a stale lock
  surviving a container restart, would look exactly like this). Tested
  directly: `docker exec vinu-components-news-api-1 python3 -c
  "from filelock import FileLock, Timeout; FileLock('/shared/
  watchlist.json.lock', timeout=3).acquire()"` — acquired immediately,
  proving the lock was free at the time of the hang. Ruled out with a
  live test, not by inspection alone.
- **Not the file-ownership issue from
  [`data-dir-host-uid-ownership-after-rebuild.md`](data-dir-host-uid-ownership-after-rebuild.md)**
  — that was already fixed project-wide before this hang was observed,
  and `news-api`/`stock-api` were both confirmed healthy and writing to
  their own data files fine at the time.

## Why it mattered

Same "healthy container, dead background loop" shape as
[`freshness-recompute-scan-never-started-in-production.md`](freshness-recompute-scan-never-started-in-production.md)'s
"Later correction" section — `docker compose ps` and `/news/health`
report normally throughout (they only check the HTTP server), giving zero
signal that ingestion, watchlist-driven backfill, and (as a direct
consequence, since it runs later in the same loop iteration) the new
automatic FinBERT scoring have all silently stopped. Left alone, this
would present as "the news pipeline looks fine" indefinitely while no new
data of any kind accumulates.

## What was done this run (mitigation, not a fix)

`docker compose restart news-api` — cleared whatever state the hang was
in; confirmed the ingest loop resumed and produced new log output after
restart. No data was lost: `run_backfill_single()` resumes from each
ticker's persisted `backfilled_up_to_ts`, not from scratch.

## Not fixed — needs a follow-up session with time to actually reproduce it

Root cause is genuinely unknown, not just undocumented. Worth checking,
in order of suspicion given the "idle CPU, zero log output, zero
exception" signature (points at something blocking inside a syscall the
Python-level retry/timeout logic doesn't see, not the application logic
itself):

- SQLite `busy_timeout`/lock contention between the `serve` process and
  the `ingest` process on the same `news.db` file under WAL mode — an
  unbounded wait on a database lock would produce exactly this signature
  (idle CPU, no exception, no log line) and neither process's code was
  audited for this during this pass.
- Whether `requests`' `timeout=` parameter is actually being honored for
  the *connect* phase specifically on this network path (`host.docker.
  internal` DNS resolution or the underlying `urllib3` connection pool)
  — a hang during DNS resolution or connection-pool exhaustion can occur
  before `requests`' read-timeout logic ever engages.
- Add a `logging.info` at the very start of `run_backfill_single()` (one
  line, low cost) so a future recurrence at least pins down whether it's
  stuck before or inside that function — currently there is no log
  evidence distinguishing "never called" from "called and stuck on the
  first line."
