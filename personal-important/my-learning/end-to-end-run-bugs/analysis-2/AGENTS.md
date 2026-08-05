# Analysis-2: End-to-End Run Bug Fixes

## Context

This directory documents bugs found during end-to-end testing of the research pipeline.
These bugs were discovered while debugging `POST /research/run` returning
`total_iterations=0`.

## Key Findings

1. **Simulator was working** — The 422 error was fixed by prepending required imports before `exec()`
2. **LLM prompts were too large** — Refinement prompts (5,500 chars) caused 363s ReadTimeout
3. **Container file placement** — `debug.py` needed to be at package root (`/app/vinu-infra/`), not nested (`/app/vinu-infra/vinu_infra/`)
4. **LLM server is single-threaded** — qwen36-35B processes requests sequentially, 3 concurrent calls queue up (30-35s each)

## Process

For each bug:
1. Read the problem description
2. Understand the root cause
3. Review the actual fix
4. Run verification steps
5. Update STATUS.md if needed

## Commands

```bash
# Test research pipeline
docker exec -e VINU_DEBUG=true vinu-components-research-api-1 python3 -u -c "
import asyncio
from vinu_research.service import ResearchService
from vinu_research.config import load_config

async def test():
    cfg = load_config()
    svc = ResearchService(config=cfg)
    result = await svc.run_research(
        user_idea='mean-reversion JPM RSI SMA',
        symbol='JPM',
        from_date='2026-04-01',
        to_date='2026-07-23',
        indicators=['sma_20', 'sma_50', 'rsi_14'],
    )
    print(f'status={result[\"status\"]} iters={result[\"total_iterations\"]}')
    await svc.close()

asyncio.run(test())
"

# Check LLM logs
docker exec vinu-components-research-api-1 python3 -c "
import json
with open('/data/llm_calls.jsonl') as f:
    for i, line in enumerate(f, 1):
        e = json.loads(line)
        print(f'{i}: {e[\"duration_sec\"]}s success={e[\"success\"]} prompt={len(e.get(\"user_prompt\",\"\"))}c')
"

# Check container health
docker ps --filter name=vinu-components --format "{{.Names}}\t{{.Status}}"

# Rebuild containers
docker compose up -d --build research-api simulator-api
```

## Notes

- All containers use read-only rootfs — use `docker compose up -d --build` to deploy changes
- The LLM server runs on `host.docker.internal:8009` (not localhost)
- `pip install -e /app/vinu-infra` creates editable install — files at `/app/vinu-infra/` root level
- Module placement matters: `debug.py` must be at `/app/vinu-infra/debug.py`, not `/app/vinu-infra/vinu_infra/debug.py`
