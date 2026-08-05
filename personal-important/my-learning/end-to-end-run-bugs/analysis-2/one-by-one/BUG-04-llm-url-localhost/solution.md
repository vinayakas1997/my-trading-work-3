# BUG-04 🔴 LLM URL Uses localhost in Docker

**Component:** `vinu-components`
**Files Changed:** `vinu-components/.env`
**Date Found:** 2026-07-23
**Date Fixed:** 2026-07-23

## Problem

The LLM base URL was set to `http://localhost:8009/v1`, which doesn't resolve inside
Docker containers. `localhost` inside a container refers to the container's own network
namespace, not the host machine. This caused all LLM calls to fail with connection errors.

## Root Cause

`.env:9` had `VINU_LLM_BASE_URL=http://localhost:8009/v1`. Docker containers need
`host.docker.internal` (or the host's actual IP) to reach services running on the host.

## Suggested Fix

Change `.env` URL from `localhost` to `host.docker.internal`.

## Actual Fix

Changed `.env:9`:
```bash
# Before
VINU_LLM_BASE_URL=http://localhost:8009/v1

# After
VINU_LLM_BASE_URL=http://host.docker.internal:8009/v1
```

## Verification

1. Run `docker exec research-api python3 -c "import httpx; httpx.get('http://host.docker.internal:8009/v1')"`
2. Confirm LLM calls succeed from inside containers
3. Run full research pipeline — confirm LLM generates strategies

## Lessons Learned

- `localhost` inside Docker ≠ host machine
- Use `host.docker.internal` for host access (Linux requires `--add-host` flag)
- The vinu-infra `client_async.py` has `alternative_urls()` that handles this fallback,
  but the primary URL in `.env` should still be correct
