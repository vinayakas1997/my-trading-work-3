---
name: data-root-docker-path-mismatch
status: fixed
severity: blocked-6-of-10-services-in-docker-mode
---

# Bug: the shared `.env`/`.env-example` template's data-root paths were host-mode paths, not Docker paths

## What was wrong

After fixing the CRLF entrypoints
([`entrypoint-sh-crlf-line-endings.md`](entrypoint-sh-crlf-line-endings.md)),
`news-api` still crashed, now with a different error:

```
OSError: [Errno 30] Read-only file system: '../data'
```

Root cause: `vinu-components/.env-example`'s per-service data-path
variables were written as **relative, host-mode paths** —
`VINU_NEWS_DB_PATH=../data/news/news.db`,
`VINU_STOCK_DATA_ROOT=../data/stock-price`,
`VINU_FEATURES_DATA_DIR=../data/features`,
`VINU_STRATEGY_DATA_ROOT=../data/strategy`,
`VINU_SIMULATOR_DATA_ROOT=../data/simulator`,
`VINU_RESEARCH_DATA_ROOT=../data/research` — correct only if a service is
run directly on the host, from inside its own directory, so `../data/...`
resolves to the sibling `vinu-components/data/...` folder.

In Docker, every service's Dockerfile already sets the *correct* absolute
default (e.g. `vinu-news/Dockerfile`: `ENV VINU_NEWS_DB_PATH=/data/news.db`,
matching the `./data/news:/data` bind mount in `docker-compose.yml`). But
`env_file: .env` in `docker-compose.yml` supplies these variables at
container runtime, and runtime environment variables override the image's
build-time `ENV` defaults — so the relative host-mode value from `.env`
silently clobbered the correct Docker-mode default baked into every one of
these images. Each container's `WORKDIR` is one level deeper than the
relative path assumes (e.g. `/app/vinu-news`, not `/app`), so
`../data/...` resolved to a path on the container's **read-only root
filesystem**, not the writable `/data` mount — exactly like the
already-documented `vinu-agent` case
(`VINU_AGENT_DATA_ROOT`'s comment in `.env-example`), just not yet applied
to the other six services.

One more, smaller finding along the way: `VINU_CORRELATION_DATA_ROOT` (the
name this template used for `vinu-initial-analysis`) is **not read
anywhere** in `vinu_initial_analysis`'s code — grepped, zero matches. The
real variable is `VINU_INITIAL_ANALYSIS_DATA_ROOT`. This particular one
never actually broke anything only by luck: since the wrong name was never
read, the Dockerfile's correct `/data` default was never overridden.

## Why it mattered

This blocked **6 of the 10 services** the same way — `vinu-news`,
`vinu-stock-price`, `vinu-tools`, `vinu-strategy`, `vinu-simulator`,
`vinu-research` — every one of them would have crash-looped on storage
initialization the moment their container actually tried to write
anything, right after the CRLF fix cleared the first blocker.
`vinu-initial-analysis` happened to be spared by the unrelated
variable-name mismatch above, not because its entry was actually correct.

## What was fixed

In both `vinu-components/.env-example` and the real (gitignored)
`vinu-components/.env`:

- `VINU_NEWS_DB_PATH` → `/data/news.db`
- `VINU_STOCK_DATA_ROOT` → `/data`, `VINU_STOCK_META_DB_PATH` → `/data/meta.db`
- `VINU_FEATURES_DATA_DIR` → `/data`, `VINU_FEATURES_META_DB_PATH` → `/data/meta.db`
- `VINU_CORRELATION_DATA_ROOT` (wrong name, unused) → renamed to
  `VINU_INITIAL_ANALYSIS_DATA_ROOT=/data` (the name the code actually reads)
- `VINU_STRATEGY_DATA_ROOT` → `/data`
- `VINU_SIMULATOR_DATA_ROOT` → `/data`
- `VINU_RESEARCH_DATA_ROOT` → `/data`

Added a comment block above the `vinu-news` section in `.env-example`
explaining the constraint (mirroring the existing `vinu-agent` comment) and
noting that host-mode (non-Docker) execution should override back to each
service's own relative path.

**Not chased further, confirmed harmless**: every service's
`VINU_*_HOST=127.0.0.1` entries in this same template are also host-mode
values, but every `entrypoint.sh` (and the `strategy-api`/`simulator-api`
`command:` in `docker-compose.yml`) hardcodes `--host 0.0.0.0` on the CLI
invocation directly, which wins over any env-var-based default. Confirmed
by reading all 7 entrypoint scripts — none of them read the `HOST` env var
at all. Left as-is; flagged here so it isn't mistaken for the same class of
bug on a future pass.

## What was achieved

All 10 containers reached `healthy` for the first time in this pass —
`docker compose ps` shows every service `Up ... (healthy)`, confirmed with
direct health-endpoint checks on `initial-analysis`, `research`, and
`agent`. This, combined with the CRLF fix, is what actually got
`01-setup-and-rebuild.md`'s stack past its first checkbox.
