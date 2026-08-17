---
name: first-small-e2e-check-plan
status: not-started
purpose: the ordered plan for the first small end-to-end check of the 3 in-scope vinu components against real Alpaca data and real (or honestly-labeled fallback) model weights — one ticker, thin slice, before any wider test or before writing the deeper per-angle explanation docs discussed separately.
---

# First Small E2E Check — Plan

## Why this exists

Per `../03-actual-plan-findings/04-build-status.md`, almost nothing in
this project has been run against real data yet: `vinu-stock-price` has
zero Parquet files on disk, `vinu-initial-analysis` has no real run
outputs, code/tests are mature but largely unexercised against a real
Alpaca feed. This folder is the plan for the smallest real slice that
proves the pipeline actually works end-to-end — **one ticker, one
recent window, a handful of angles** — before scaling to all 32 methods
or all tickers, and before investing in the richer per-angle explanation
docs discussed separately (that work needs real observed output ranges
to be honest, which this check produces).

**Scope**: only the 3 stage-1 containers that actually match the current
build — `news-api`, `stock-api`, `initial-analysis-api`. The other 7
services in the root `docker-compose.yml` (`features-api`,
`strategy-api`, `simulator-api`, `portfolio-api`, `research-api`,
`live-api`, `agent-api`) are later-stage and not part of this check.
`vinu-infra`/`vinu-tools` are shared libraries imported by the 3
containers, not separate services — they're verified inline (import
works, `require_data_root`/`SQLiteBackend`/GARCH call succeed) inside
each component's own check file, not as standalone deploys.

## Order of operations

### 0. Copy `.env-example` to `.env` first

Every step below (`make models`, container boot, Alpaca fetch,
`VINU_STAGE1_START_DATE`) reads from `.env`, which is gitignored and
does not exist until created:

```
cd vinu-components
cp .env-example .env
```

Then fill in real values in `.env` (never edit `.env-example` itself
with real secrets — it stays a committed template): at minimum
`ALPACA_API_KEY`, `ALPACA_API_SECRET` (see step 4 below).
`VINU_STAGE1_START_DATE` already comes from `.env-example` set to a
short ~2-week test window rather than the real `2022-01-01` — see step
2, don't change it back for this check.

If running `vinu-initial-analysis` outside Docker (e.g. directly via its
own CLI for a quick check), it also has its own
`vinu-initial-analysis/.env.example` — same copy-then-fill pattern,
scoped to just that component's variables (relative `../data/...` paths
instead of Docker's `/data`).

### 1. Download models first — before touching containers

`news-api` and `initial-analysis-api` both mount
`./data/models:/models:ro` **read-only** (see `docker-compose.yml`
lines ~14, ~131). `ensure_model()`'s auto-download-if-missing fallback
(`vinu-infra/models.py`) **cannot work inside these containers** — a
write to a read-only mount fails. Models must be fully downloaded on the
**host** first:

```
cd vinu-components
make models        # installs vinu-infra[models], runs `vinu-models --dir ./data/models`
make models-list    # confirm what landed
```

Expect real weights for: `finbert`, `chronos-t5-tiny`,
`timesfm-2.5-200m-pytorch`, `timer-timerxl`, `kronos`, `kronos-tokenizer`
(these 5 angles load `model_backend: pretrained`). `moirai`, `moment`,
`lag-llama` will also download (weights-only, loaders intentionally not
wired — see `../03-actual-plan-findings/06-models-download.md`) — their
angles will still report `fallback_proxy`, that's expected, not a bug.

**Check**: does `data/models/` even exist at the start of this check, or
is this a fresh checkout where it needs creating from scratch? Either
way `make models` should handle it (confirmed in code:
`ensure_model()`'s `path.mkdir(parents=True, exist_ok=True)` creates the
full missing chain before downloading) — but confirm it actually does
on a real run, don't just trust the code read.

### 2. `start_date = 2022-01-01` — now a real, readable env var

**Original finding (before the fix below): no, it wasn't set anywhere.**
`2022-01-01` only ever appeared as an unrelated backtest label in
`vinu-research` and as an example string in an API docstring in
`vinu-stock-price` — no config constant, no env var, no enforcement
anywhere.

**Fixed**: `VINU_STAGE1_START_DATE=2022-01-01` is now a real env var —
by decision, **not hardcoded in code**, so it's visible/auditable in one
place (`.env`) rather than buried in a Python constant:
- `vinu-initial-analysis/.env.example` and the root `.env-example` both
  declare it (with a comment: never change this in a real deployment —
  it's what keeps every ticker's run comparable to every other run).
- `VinuInitialAnalysisConfig.stage1_start_date`
  (`vinu-initial-analysis/vinu_initial_analysis/config.py`) reads it via
  `os.getenv("VINU_STAGE1_START_DATE", "2022-01-01")` — defaults to the
  same fixed date if somehow unset, so a missing `.env` line degrades to
  the correct value rather than breaking.

**For this small E2E plumbing check specifically**: `.env-example` (both
the root one and `vinu-initial-analysis/.env.example`) has the real
`VINU_STAGE1_START_DATE=2022-01-01` line **commented out**, replaced
with a temporary override `VINU_STAGE1_START_DATE=2026-07-23` (~2 weeks
before this plan was written) — a short window so this check is fast to
run instead of implying the full 2022→now history. This is a
plumbing-check-only override, clearly marked in both `.env-example`
files. **Before any real/production use, uncomment the real
`2022-01-01` line and remove/comment the test override.**

**Check during this run**: confirm `config.stage1_start_date` actually
resolves to the value genuinely present in your `.env` (whichever of the
two you're using — test override or real value), not silently falling
back to the hardcoded default because the line was missed when copying
from `.env-example`. Note: this config field exists and is readable
now, but **nothing in the API/trigger path validates or enforces it
yet** — a `trigger` call can still pass any `{time-range}` regardless of
this value. That enforcement is a separate, still-open follow-up, not
done as part of this env-var fix. When triggering angles in step 5
below, still pass the window explicitly by hand; don't rely on this
value being enforced anywhere yet.

### 3. Confirm `end_date = last completed quarter` — IS IT ACTUALLY SET?

**Finding: also no.** No quarter-boundary calculator exists anywhere in
the codebase (repo-wide search for `quarter` in `.py` files turns up
only unrelated hits — a Kelly-fraction comment in
`vinu-simulator/.../sizing.py`, docstring mentions of "scheduled
quarterly" as a *concept* in `vinu_initial_analysis/storage/parquet.py`
and `vinu_news/server/routes_v1.py`). Nothing computes "whichever
calendar quarter has just closed" and nothing schedules a run against
it. `tier2` (the storage tier meant to hold this scheduled quarterly
result) exists and works as a storage concept, but nothing populates it
on the described cadence yet.

For this E2E check: **compute the current quarter boundary by hand**
(today's date is what determines it) and pass it explicitly as the
`{time-range}` end when triggering. Don't expect the system to derive
it.

### 4. Alpaca details

Required env vars (from `.env-example` at repo root, shared by both
`news-api` and `stock-api`):
```
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_DATA_BASE_URL=https://data.alpaca.markets
```
- Confirm real (non-empty, non-placeholder) values are in `.env` before
  starting containers — both `vinu-news/vinu_news/config.py` and
  `vinu-stock-price/vinu_stock/config.py` read these via
  `os.environ.get(..., "")`, i.e. **silently default to an empty
  string** rather than failing fast if unset. That means a missing key
  won't crash the container at boot — it'll crash (or silently return
  no data) on the first real fetch. Check for this explicitly rather
  than assuming boot-success means the credentials are good.
- Per `../limitations_and_other_info.md` #3, Alpaca is the *only* data
  source in scope — no fallback vendor. If the key is wrong/rate-limited,
  there's nothing else to fall back to; that failure mode needs to be
  visible, not swallowed.
- `vinu-stock-price` only fetches `1min` bars directly (per
  `../03-actual-plan-findings/03-storage-design.md` #3); everything
  coarser is resampled locally. Don't request `5min`/`1hr`/etc. straight
  from Alpaca — confirm the resample path is what's actually exercised.

### 5. Small pipeline — the actual E2E flow

One ticker (suggest `AAPL` — liquid, always has recent bars/news), one
short real window (last few trading days, not the full 2022→now
history — this is a plumbing check, not a full backfill):

1. `stock-api`: trigger a real `1min` fetch for the window, confirm
   bars land on disk (`prices/1m/{SYMBOL}/live/{year}_{YYYYMMDD}.parquet`
   — corrected 2026-08-06 to match real code, see
   `../03-actual-plan-findings/03-storage-design.md` #4), confirm a
   `5min`/`1hr` resample read actually derives from that data (not
   another independent fetch).
2. `news-api`: confirm real articles for the same ticker/window are
   ingested and at least one of the 9 Section-1 methods (e.g.
   `event-type-classification`) returns a non-fallback result over them.
3. `initial-analysis-api`: `trigger` a small spread of angles against
   real price data written in step 1 — one classical (`arima`), one
   trained-from-scratch neural (`lstm`), one genuinely `pretrained`
   foundation model (`chronos`) — via the new
   `/v1/stage1/vinu-initial-analysis/trigger/...` route. Poll with the
    returned `run_id` until `status: ok`. Confirm the result lands in
    `tier3` (triggered), confirm a plain `fetch` (no run-id) against
    `tier2` correctly 404s (nothing's been scheduled there yet — expected,
    see step 3 above).
    > **Correction found during the run (round 1):** the plain tier2
    > `fetch` does **not** 404 — `vinu-initial-analysis`'s
    > `entrypoint.sh` starts `vinu-initial-compute --all --continuous &`,
    > so a tier2 scheduler is genuinely running inside the container and
    > populating tier2 (full-history runs, `from/until=None`). A plain
    > fetch returns 200 with the scheduler's own run (e.g. AAPL arima
    > `503103784abd`). The 404 expectation was based on the older
    > assumption that nothing populated tier2; update this step for any
    > future round.
4. Spot-check the actual numeric output of each of the 3 angles against
   the real price series by eye — does the ARIMA forecast look like a
   sane extrapolation of the real closes, does Chronos's output track
   the recent trend at all? This is the first real signal on whether
   the compute logic is trustworthy, not just "did it run without
   throwing."

Full detail + checklists for each component's part of this: see
`01-vinu-news.md`, `02-vinu-stock-price.md`, `03-vinu-initial-analysis.md`.

### 6. Container cleanup, then deploy only the 3 in-scope containers

```
cd vinu-components
docker compose down          # remove any existing/stale containers first — don't leave old state around
docker compose up -d --build news-api stock-api initial-analysis-api
```

**Do not** `docker compose up` the full stack — `features-api`,
`strategy-api`, `simulator-api`, `portfolio-api`, `research-api`,
`live-api`, `agent-api` are later-stage, not part of this check, and
some may not even build cleanly against the current `.env-example`
(several reference cross-service URLs for containers that won't be
running). Bringing them up risks noise (crash-looping containers) that
has nothing to do with what this check is verifying.

## Related files

- `AGENTS.md` — directions for whichever agent actually executes this
  check, since this plan may be run by a different agent/session than
  the one that wrote it
- `01-vinu-news.md` / `02-vinu-stock-price.md` / `03-vinu-initial-analysis.md`
  — per-component checklists + round-wise `BUGS-N`/`FIXES-N` logs
- `04-round-2-tier2-fix-verification.md` — Round 1 found and fixed a
  real bug (tier2 scheduler dedup logic never recomputing stale data,
  see `03-vinu-initial-analysis.md`'s `BUGS-1`/`FIXES-1`); this file is
  the narrow, standalone Round 2 re-check for that specific fix — read
  it instead of repeating this whole plan's step 5 if a Round 1 entry
  already exists
- `../03-actual-plan-findings/04-build-status.md` — why this check
  matters (confirms how little of the pipeline has touched real data)
- `../limitations_and_other_info.md` — the constraints this check is
  measured against (Alpaca-only, fixed start date, quarterly cadence,
  2-3GB model cap)
- `../03-actual-plan-findings/06-models-download.md` — which models are
  genuinely `pretrained` vs. honestly `fallback_proxy`, relevant to step
  4's spot-check
