# Issues Index

Real bugs/defects worth fixing. One file per issue: `ISSUE-NNN-<slug>.md`.

| ID | Title | Component | Phase | Severity | Status |
|---|---|---|---|---|---|
| ISSUE-001 | Timer real model fails to load (ROFS) — leaked Windows HOME | docker-compose.yml / timer_timerxl/compute.py | 1 | HIGH | FIXED |
| ISSUE-002 | Strategy registry loads empty: strategies dir bind mount never seeded | docker-compose.yml / registry.py / .env | 2 | HIGH | FIXED (workaround) |
| ISSUE-003 | /data write permissions root-owned on 9p metadata mount | docker-compose.yml bind mounts / vinu_infra.sqlite.py | 2/3 | HIGH | FIXED (workaround) |
| ISSUE-004 | OpenRouter free-tier rate limiting floods LLM-heavy steps | vinu-news / vinu-research / vinu-agent | 3 | HIGH | OPEN (env constraint) |
| ISSUE-005 | Agent session events endpoint returns empty | vinu-agent routes_sessions.py | 2 | LOW | OPEN |
| | | | | | |

_Add a row per new issue. Use `ISSUE-000-template.md` as the template._

Related: known gaps from architecture.md §8 are tracked in `open-gaps-for-future.md` (parent folder).
