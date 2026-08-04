---
name: data-dir-host-uid-ownership-after-rebuild
status: fixed
severity: blocked-3-of-10-services-on-a-fresh-recreate
---

# Bug: bind-mounted `data/` directories were owned by the host user, not the container's `app` user, so a fresh container recreate couldn't open its own database files

## What was wrong

Running `01-setup-and-rebuild.md`'s `docker compose down && docker compose
up --build -d` on 2026-08-04 (to pick up this session's telemetry-layer
changes) left `news-api` and `stock-api` crash-looping on startup:

```
sqlite3.OperationalError: unable to open database file
```

Root cause: every container in this stack runs as a non-root `app` user
(`uid=100, gid=101`, added via `addgroup --system app && adduser --system
--ingroup app app` in each Dockerfile), with `read_only: true` and the
service's `./data/<service>:/data` bind mount as one of the only writable
paths. The host-side `data/news` and `data/stock-price` directories were
owned `1000:1000` (the host user), not `100:101`. `drwxrwxr-x` with that
ownership gives the container's `app` user (not in the owning group) only
`r-x` on the directory — enough to read existing files, not enough to open
a fresh connection or create a new one. The previous 8-hour-old containers
had kept working only because their processes already held the file open
before whatever reset the host directory ownership to `1000:1000` — a
`down`/fresh `up` forces every service to open its database file anew,
which is when the permission check actually bites.

**A second, related instance of the same class surfaced immediately
after**: `initial-analysis-api` failed the same way post-fix, but for a
different reason — `docker-compose.yml` bind-mounts
`./data/initial-analysis:/data` for this service, a path that had never
been created on disk (the service's actual historical data lived in
`./data/correlation`, an old path name left over from before a rename —
confirmed empty except for a `.gitkeep`, so nothing was lost). Docker
auto-creates a bind-mount source directory that doesn't exist yet, and
does so as `root:root`, which the container's `app` user can't write to
either.

## Why it mattered

This is the same file-ownership-blocks-writes shape as
[`data-root-docker-path-mismatch.md`](data-root-docker-path-mismatch.md)
and the `vinu-agent`/`Path.home()` issues elsewhere in this project, just
at the host-filesystem-permissions layer instead of the environment-variable
layer — and it's a real trap for *any* future `docker compose down && up`
on this stack, not a one-time fluke: nothing in the repo pins `data/`'s
ownership, so anything that resets it back to the invoking host user (a
workspace restore, a host-side script writing into `data/` as a normal
user, etc.) silently breaks the next rebuild in a way that "container
still shows healthy right now" gives zero warning about.

**Separately, and unrelated to file ownership**: `vinu-components/.env`
itself did not exist on disk at all when this rebuild started — only
`.env-example` was present, and it has blank `ALPACA_API_KEY`/
`ALPACA_API_SECRET` fields. The already-running containers still had real
credentials (confirmed via `docker exec ... env`), meaning `.env` existed
at some point after those containers were created and was later lost.
Rebuilding blind from `.env-example` would have silently disabled every
Alpaca-backed broker call. Recovered the real key/secret from
`alpaca-details/details.md` (matched what the running container already
had) rather than guessing; not re-documented as a numbered bug here since
it's a workspace-state issue, not a code bug, but recorded because the
next agent hitting a missing `.env` should look there first, not assume
`.env-example` is a safe stand-in.

## What was fixed

- `data/` (the whole tree, all 10 services' directories): re-owned to
  `100:101` via a throwaway `alpine` container bind-mounting the same host
  path and running `chown -R 100:101 /data` as root inside the container
  (the invoking host user had no `sudo`/`chown`-to-other-uid rights
  directly) — metadata-only, no file content touched.
- Re-ran the same chown after `initial-analysis-api`'s first recreate
  attempt auto-created `data/initial-analysis` as `root:root`, then
  `docker compose up -d --force-recreate` on the three affected services.
- Services that were already `Created`/`Started` against the pre-chown
  ownership needed an explicit `--force-recreate`, not just another
  `docker compose up -d` — a plain `up` does not re-check bind-mount
  permissions against an already-created container.

## What was achieved

All 10 services reached `healthy` after the ownership fix and
`--force-recreate`, confirmed via `docker compose ps` and direct health
endpoint checks on `initial-analysis`, `research`, and `agent`. No data
was lost — `data/correlation` (the orphaned old path) held nothing but a
`.gitkeep`, and every other service's bind-mounted directory kept its
existing content, only its ownership metadata changed.

## What to check on the next fresh rebuild

If `docker compose down && docker compose up --build -d` produces
`sqlite3.OperationalError: unable to open database file` (or the
initial-analysis-specific `runs.db` variant) on a service that was
previously healthy, check `stat -c "%u:%g" data/<service>` before assuming
a code regression — `100:101` is correct (every service's Dockerfile uses
the same uid/gid), anything else means the host directory's ownership
drifted and needs the same `chown -R 100:101` fix via a throwaway
container, followed by `--force-recreate` on whichever services were
already created against the wrong ownership.
