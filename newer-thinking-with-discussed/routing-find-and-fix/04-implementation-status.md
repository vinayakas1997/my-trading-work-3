# Implementation status

Updated after every piece of work. Last updated: 2026-10-04.

## Phases

| Phase | What | Status |
|---|---|---|
| 1 | Layer A: static contract scan over all 13 services (`contract_scan.py`), generated registry, findings fixed | **DONE 2026-10-04** |
| 2 | Layer B: per-connection contract (fields + example payload) in `pipeline_edges.yaml` | not started |
| 3 | Layer C: runtime shape check in the edge recorder (needs data, Phase 2 of the project) | not started |
| 4 | Run the scan as a permanent check (CI / `docker compose run`), fail on new ERRORs | not started |

(Plan and layers: `01-plan.md`. The project-wide phases are different: see `../working-rules.md`.)

## Layer A: what exists

- `vinu-components/vinu-infra/contract_scan.py` (module `vinu_infra.contract_scan`): builds each app, reads OpenAPI; parses every service's source; compares; writes `contracts.json` and `02-contract-registry.md`; exits 1 on any ERROR not allowlisted.
- Latest run: **13 services, 272 routes, 183 HTTP calls found, 177 matched to a route, 0 field problems, 1 error (allowlisted, R5), 5 external calls (INFO)**. 184 routes have no caller (R8).
- Hand-maintained inputs: `contract_allowlist.json`, `client_prefixes.json`.

## Fixes made by this work (details in `03-findings.md`)

| ID | Fix | Files (inside `vinu-components/`) |
|---|---|---|
| R1 | `/agent/notify/...` at 5 call sites | `vinu-live/vinu_live/scheduler.py`, `live_decision/poller.py`, `trade_plan/orchestrator.py`, `vinu-portfolio/vinu_portfolio/service.py` (committed ec07208f) |
| R2 | `GET /analysis/angles?active=true` + 4 callers | `vinu-initial-analysis/vinu_initial_analysis/server/routes_read.py`, `vinu-agent/vinu_agent/tools/angles_tool.py` (committed ec07208f) |
| R3 | six missing service prefixes | `vinu-agent/vinu_agent/memory/sync_service.py`, `tools/portfolio_comparison_tool.py` |
| R4 | `from_ts` / `to_ts` instead of `from` / `to` (3 methods) | `vinu-research/vinu_research/tools.py` |

## Tests

| Where | Tests |
|---|---|
| `vinu-infra/tests/test_contract_scan.py` | 15: OpenAPI read, AST read (f-strings, local URLs, dict bodies with later additions, decorators ignored, `**` dynamic), every finding kind, wildcard matching, allowlist, registry |
| `vinu-agent/tests/test_agent_service_paths.py` | 6 (R3) |
| `vinu-research/tests/test_tools_analysis_params.py` | 4 (R4) |
| earlier (R1, R2) | live and portfolio notify tests tightened; `test_angles_active_filter.py` (3); `test_angles_tool.py` (+1) |

Mutation checks: R1 (reverting one call site: 7 fail), R3 (all 6 fail), R4 (3 fail). The scanner itself was also corrected twice while building it (it first treated route decorators and external API calls as calls); the unit tests lock that in.

## Still open

- R8 (data outputs nothing reads), R9, R10 (types and responses), R11 (helper-function URLs): see `03-findings.md`.
- Layers B and C, and running the scan automatically (phases 2-4 above).
- The scan needs every service's dependencies: it was run here with a temporary environment for the agent app (`--python agent=...`).
