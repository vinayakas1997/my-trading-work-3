# Implementation status

Updated after every piece of work. Last updated: 2026-10-04.

## Phases

| Phase | What | Status |
|---|---|---|
| 1 | Layer A: static contract scan over all 13 services (`contract_scan.py`), generated registry, every finding fixed or classified | **DONE 2026-10-04** |
| 2 | Layer B: per-connection contract (fields + example payload) in `pipeline_edges.yaml` | not started |
| 3 | Layer C: runtime shape check in the edge recorder (needs data, Phase 2 of the project) | not started |
| 4 | Run the scan as a permanent check (CI / `docker compose run`), fail on new ERRORs | not started |

(Plan and layers: `01-plan.md`. The project-wide phases are different: see `../working-rules.md`.)

## Layer A: what exists

- `vinu-components/vinu-infra/contract_scan.py` (module `vinu_infra.contract_scan`, 19 tests): builds each app and reads its OpenAPI; parses every service's source; compares; writes `contracts.json` and `02-contract-registry.md`; exits 1 on any ERROR not allowlisted.
- Reads: direct calls (`.get/.post/...`, `.request`), URLs held in local variables or built from a base variable, `params=` and `json=` keys (including keys added later with `payload["x"] = ...` and annotated assignments), and helper calls whose URL is a visible argument.
- Latest run: **13 services, 272 routes, 203 calls found, 197 matched to a route, 0 field problems, 1 error (allowlisted, R5), 5 external calls (INFO), 0 routes without a classification.**
- Hand-maintained inputs, each with reasons: `contract_allowlist.json`, `client_prefixes.json`, `route_notes.json`.

## Fixes made by this work (details in `03-findings.md`)

| ID | Fix | Files (inside `vinu-components/`) |
|---|---|---|
| R1 | `/agent/notify/...` at 5 call sites | `vinu-live/vinu_live/scheduler.py`, `live_decision/poller.py`, `trade_plan/orchestrator.py`, `vinu-portfolio/vinu_portfolio/service.py` (commit ec07208f) |
| R2 | `GET /analysis/angles?active=true` + 4 callers | `vinu-initial-analysis/vinu_initial_analysis/server/routes_read.py`, `vinu-agent/vinu_agent/tools/angles_tool.py` (commit ec07208f) |
| R3 | six missing service prefixes | `vinu-agent/vinu_agent/memory/sync_service.py`, `tools/portfolio_comparison_tool.py` (commit 3ec73c16) |
| R4 | `from_ts` / `to_ts` instead of `from` / `to` (3 methods) | `vinu-research/vinu_research/tools.py` (commit 3ec73c16) |
| R12 | strategy clients: `from_ts` / `to_ts`; features client no longer takes a window | `vinu-strategy/vinu_strategy/clients/correlation_client.py`, `features_client.py` |

## Tests

| Where | Tests |
|---|---|
| `vinu-infra/tests/test_contract_scan.py` | 19: OpenAPI read, AST read (f-strings, local URLs, dict bodies with later additions, decorators ignored, `**` dynamic), helper calls (and log lines ignored), every finding kind, wildcard matching, route notes, allowlist, registry |
| `vinu-agent/tests/test_agent_service_paths.py` | 6 (R3) |
| `vinu-research/tests/test_tools_analysis_params.py` | 4 (R4) |
| `vinu-strategy/tests/test_client_query_names.py` | 2 (R12) |
| earlier (R1, R2) | live and portfolio notify tests tightened; `test_angles_active_filter.py` (3); `test_angles_tool.py` (+1) |

Suite totals: `vinu-infra` 430, `vinu-strategy` 154 (+ the same 10 environment errors as before), `vinu-agent` 1533 (same 16 failed / 2 errors as before), `vinu-research` 1306 (the old `test_empty_meanings` failure and one flaky SQLite thread-safety test).
Mutation checks: R1 (reverting one call site: 7 fail), R3 (all 6 fail), R4 (3 fail), R12 (1 fails). The scanner itself was corrected several times while building it (it first treated route decorators and external API calls as calls, and missed helper calls); the unit tests lock those in.

## Still open

- D1-D4 in `03-findings.md`: four decisions (use news impact? expose calibration and graveyard to an agent? keep the older analysis events view? which stage-1 API is canonical?). None is a bug.
- Layers B and C, and running the scan automatically (phases 2-4 above).
- R9-R11, the known limits of the scan.
- The scan needs every service's dependencies; here it was run with a temporary environment for the agent app (`--python agent=...`).
