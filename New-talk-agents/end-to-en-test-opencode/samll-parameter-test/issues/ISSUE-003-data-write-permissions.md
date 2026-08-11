# ISSUE-003 — /data write permissions root-owned on 9p metadata mount

- **Component:** docker-compose.yml bind mounts (`./data/*:/data`) on Docker Desktop 9p/grpc-fuse `metadata` mount; vinu-initial-analysis `storage/orchestration_registry.py` + vinu-research `vinu_infra/sqlite.py`
- **Phase found:** 2/3 (Block 3 + research run)
- **Severity:** HIGH

## Description
`./data/*` host directories are created root-owned (mode 755) by the bind-mount setup on Docker Desktop. Containers run as uid 100 (`app`). SQLite can create files but WAL-mode opens of pre-existing DBs (`PRAGMA journal_mode=WAL`) fail with `sqlite3.OperationalError: unable to open database file` because the `-wal`/`-shm` sidecar creation needs write on the directory.

Affected:
- initial-analysis: `sqlite3.OperationalError: unable to open database file` at `record_run` writing `/data/vinu_initial_analysis_runs.db`.
- research: same error at `ResearchStorage.is_symbol_exhausted` → `_get_conn` on `/data/research_meta.db` (interesting: the DB itself is app-owned 644, but opening still failed until `/data` was made 777 — the WAL sidecar create is what fails).

## Steps to reproduce
1. Fresh checkout, `docker compose up -d`.
2. `docker compose exec initial-analysis-api python -c "import sqlite3; sqlite3.connect('/data/x.db'); c=sqlite3.connect('/data/x.db'); c.execute('PRAGMA journal_mode=WAL')"` (as `app`).
3. Or just run the analysis / research run.

## Actual
```
sqlite3.OperationalError: unable to open database file
```

## Expected
SQLite opens and WAL mode works as the `app` user.

## Impact
Both initial-analysis and research fail to persist; whole analysis/research pipeline blocked.

## Suggested fix
Ensure host `./data/*` dirs are writable by uid 100 before `up` (e.g. chmod 777 in a preflight script or set `user:` in compose, or a Dockerfile entrypoint that `chmod 777 /data` at start). The fix is not in repo code — it's an environment/compose setup issue.

## Status
FIXED (workaround: `docker compose exec -u root <svc> chmod 777 /data` per service; persists through 9p metadata).

## Evidence
- `docker compose logs research-api` — traceback at `sqlite.py:37 PRAGMA journal_mode=WAL`
- `/tmp/walcheck.py` — app user can create+WAL a new DB but cannot open the pre-existing `research_meta.db`
