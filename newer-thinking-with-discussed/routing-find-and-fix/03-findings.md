# Findings

Status: **FIXED** (code changed, test added, mutation-checked) · **ALLOWED** (correct to leave, reason recorded) · **OPEN** (found, not changed).
Found by the Phase 1 wiring check (2026-10-04) and the contract scan built in this folder.

## Fixed

| ID | What was wrong | Where | Effect | Test |
|---|---|---|---|---|
| R1 | Alerts posted to `{agent_api_url}/notify/...` but the agent serves `/agent/notify/...` (and `VINU_AGENT_API_URL` has no `/agent`). | vinu-live `scheduler.py` (x2), `live_decision/poller.py`, `trade_plan/orchestrator.py`; vinu-portfolio `service.py` | 404, swallowed as a WARNING: drift, stuck-decision, broker-unreachable and symbol-conflict alerts were never delivered. | live and portfolio notify tests now require the exact `/agent/notify/...` path; reverting one call site fails 7 tests |
| R2 | `GET /analysis/angles` listed all 31 angles (11 model, 3 permanently disabled) whatever the model policy; the agent's coverage gate and `get_all_angles` counted them. | vinu-initial-analysis `routes_read.py`, vinu-agent `angles_tool.py` (4 calls) | "every angle has data" could never be true. | `test_angles_active_filter.py` (3), `test_angles_tool.py` (+1) |
| R3 | Six agent calls omitted the service prefix: `{research}/runs`, `{research}/artifacts`, `{simulator}/runs`, `{news}/search` (memory sync) and `{portfolio}/state`, `{research}/artifacts` (compare_portfolio). Configured base URLs are bare hosts. | vinu-agent `memory/sync_service.py`, `tools/portfolio_comparison_tool.py` | 404 whenever the in-process path was unavailable (separate containers): memory sync and portfolio comparison silently returned nothing. The old tests mocked `get` without looking at the URL. | `test_agent_service_paths.py` (6); all 6 fail when the prefixes are removed |
| R4 | Research asked initial-analysis for story / drawdown / correlation over its research window with query names `from` / `to`; the routes declare `from_ts` / `to_ts`. | vinu-research `tools.py` (3 methods) | The window was silently ignored: research and its risk critic got the whole history, including data after the window being tested (look-ahead). | `test_tools_analysis_params.py` (4); 3 fail when reverted |

## Allowed

| ID | Finding | Why it is correct to leave |
|---|---|---|
| R5 | `vinu-agent/vinu_agent/agent/llm.py:49 GET /models` reported as "no route". | It is the LLM provider's model-list endpoint, not the new `vinu-models` service; it only looks like one because that service is also mounted under `/models`. In `contract_allowlist.json`. |
| R6 | 5 calls that start with no service prefix: Ollama `/api/chat`, LLM `/chat/completions` (x2), Alpaca `/v1beta1/news`, `/v1beta1/options/snapshots/{}`. | External APIs; reported as INFO, never an error. |
| R7 | 4 calls through clients whose base URL carries the service prefix (simulator `StrategyClient` under `/strategy`, research `_features_client` under `/features`). | Verified against each constructor and listed in `client_prefixes.json`; the scan then checks them like every other call (all match, `indicators` is a declared query). |

## Open (found, not changed)

| ID | What | Notes |
|---|---|---|
| R8 | **184 of 272 routes have no caller in the code.** Most are operator routes (enable / disable, settings, triggers, history). The ones that are data outputs with no consumer and could be missing agent tools are listed in `../the-inconsistencies-v2/04-implementation-status.md`, "Phase 1 wiring check". | The full per-route list is in `02-contract-registry.md` (column "Called by": **nobody**). |
| R9 | 1 call is only partly checked: `vinu-live/.../bars_client.py:37` builds `params` with a conditional `**`, so only its known keys are checked (they match). | By design (the `closed_only` option). |
| R10 | Field **types** and the **response** a caller reads are not checked. | Layer A checks that fields exist. Layers B and C in `01-plan.md`. |
| R11 | Calls whose URL goes through a helper function (for example `_fetch_json(url, ...)`) are not seen by the scan. | A wrapper's own call is seen only if the URL is built in the same function. |
