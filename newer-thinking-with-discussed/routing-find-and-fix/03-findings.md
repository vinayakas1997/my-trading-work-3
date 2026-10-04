# Findings

Status: **FIXED** (code changed, test added, mutation-checked) · **ALLOWED** (correct to leave, reason recorded) · **DECISION** (not a bug: needs your call, see `route_notes.json`) · **OPEN** (known limit of the scan).
Found by the Phase 1 wiring check (2026-10-04) and the contract scan built in this folder.

## Fixed

| ID | What was wrong | Where | Effect | Test |
|---|---|---|---|---|
| R1 | Alerts posted to `{agent_api_url}/notify/...` but the agent serves `/agent/notify/...` (and `VINU_AGENT_API_URL` has no `/agent`). | vinu-live `scheduler.py` (x2), `live_decision/poller.py`, `trade_plan/orchestrator.py`; vinu-portfolio `service.py` | 404, swallowed as a WARNING: drift, stuck-decision, broker-unreachable and symbol-conflict alerts were never delivered. | live and portfolio notify tests now require the exact `/agent/notify/...` path; reverting one call site fails 7 tests |
| R2 | `GET /analysis/angles` listed all 31 angles (11 model, 3 permanently disabled) whatever the model policy; the agent's coverage gate and `get_all_angles` counted them. | vinu-initial-analysis `routes_read.py`, vinu-agent `angles_tool.py` (4 calls) | "every angle has data" could never be true. | `test_angles_active_filter.py` (3), `test_angles_tool.py` (+1) |
| R3 | Six agent calls omitted the service prefix: `{research}/runs`, `{research}/artifacts`, `{simulator}/runs`, `{news}/search` (memory sync) and `{portfolio}/state`, `{research}/artifacts` (compare_portfolio). Configured base URLs are bare hosts. | vinu-agent `memory/sync_service.py`, `tools/portfolio_comparison_tool.py` | 404 whenever the in-process path was unavailable (separate containers): memory sync and portfolio comparison silently returned nothing. The old tests mocked `get` without looking at the URL. | `test_agent_service_paths.py` (6); all 6 fail when the prefixes are removed |
| R4 | Research asked initial-analysis for story / drawdown / correlation over its research window with query names `from` / `to`; the routes declare `from_ts` / `to_ts`. | vinu-research `tools.py` (3 methods) | The window was silently ignored: research and its risk critic got the whole history, including data after the window being tested (look-ahead). | `test_tools_analysis_params.py` (4); 3 fail when reverted |
| R12 | vinu-strategy's `CorrelationClient` sent `from` / `to` (routes declare `from_ts` / `to_ts`); `FeaturesClient` sent `from` / `to` to `/features/{symbol}`, which has no window at all. | vinu-strategy `clients/correlation_client.py`, `clients/features_client.py` | Latent (the strategy service calls them without a window today), but any caller passing a window would have had it silently dropped. The features client no longer accepts a window it cannot honour. | `test_client_query_names.py` (2); fails when reverted |

## Allowed

| ID | Finding | Why it is correct to leave |
|---|---|---|
| R5 | `vinu-agent/vinu_agent/agent/llm.py:49 GET /models` reported as "no route". | It is the LLM provider's model-list endpoint, not the new `vinu-models` service; it only looks like one because that service is also mounted under `/models`. In `contract_allowlist.json`. |
| R6 | 5 calls that start with no service prefix: Ollama `/api/chat`, LLM `/chat/completions` (x2), Alpaca `/v1beta1/news`, `/v1beta1/options/snapshots/{}`. | External APIs; reported as INFO, never an error. |
| R7 | Calls through clients whose base URL carries the service prefix (simulator `StrategyClient` under `/strategy`, research `_features_client` under `/features`). | Verified against each constructor and listed in `client_prefixes.json`; the scan then checks them like every other call. |

## Decisions (not bugs)

Routes nothing in the code calls: **165 of 272**, every one classified in `02-contract-registry.md` (rules in `route_notes.json`): 65 operator-action (state-changing, used by a person or the UI), 85 human-view (read-only views, including the visibility routes built in this project), 3 file-read (the consumer reads the same store directly), 2 covered (another route already gives the consumer the data), and **10 candidate-gap**:

| ID | Routes | The question |
|---|---|---|
| D1 | `GET /news/high-impact`, `/news/stats/ticker/{symbol}` | News impact and threat classification is stored and shown but no gate or agent reads it. Should a gate or the live-decision agent use it? |
| D2 | `GET /research/angle-calibration/{angle}`, `/research/candidate-graveyard/{symbol}` | Written and used in-process; nothing reads these views. Should an agent? |
| D3 | `GET /analysis/events/{ticker}` | Older analysis view; research and strategy read story / drawdown / correlation / angle instead. Still needed? |
| D4 | the four `GET /v1/stage1/.../fetch` and `factsheet` routes (stock-price, news, initial-analysis) | The positional stage-1 API exists beside the older `/analysis`, `/stock`, `/news` routes, but the pipeline still reads the older ones (only `latest-run` is used). Which API is the canonical one? |

## Found by layer B

| ID | Status | What | Effect |
|---|---|---|---|
| R13 | OPEN (low) | `GET /portfolio/risk/status` returns the allocation itself (`status: empty`, no `symbols`, no `aggregate`) when no strategy is active. The order guard reads `budget.get("symbols", [])`, so "portfolio empty" and "this symbol has no open position" look the same and the order passes the risk-budget check. | Fail-open, and with no active strategy there is no budget to enforce, so it is probably right. Recorded because layer B made the two shapes visible (`RiskStatus` documents it); a decision, not a fix. |

## Open (limits of the scan)

| ID | What | Notes |
|---|---|---|
| R9 | 1 call is only partly checked: `vinu-live/.../bars_client.py:37` builds `params` with a conditional `**`, so only its known keys are checked (they match). | By design (the `closed_only` option). |
| R10 | Field **types** and the **response** a caller reads are not checked by the scan. | Layer B now covers the response shape and types of 15 connections (`edge_contracts.py`); layer C (real payloads) is not built. |
| R11 | A URL built inside one helper and passed to another, or a body assembled from `**kwargs`, is not checked field by field. | Helper calls whose URL is a visible argument (`_fetch_json(f"{base}/..")`, `_post(client, "/..")`) are now seen and checked for path and method; their fields count as dynamic and are not compared. |
