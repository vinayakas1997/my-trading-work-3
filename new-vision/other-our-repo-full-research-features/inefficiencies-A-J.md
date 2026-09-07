# Inefficiencies A-J — Pipeline Shortcomings After A1-B Clean State (2026-09-07)

> Companion to `pending-items-to-be-implemented.md` Status 2026-09-07 (Rows 1-16 + B20/B21). These A-J are throughput/cost inefficiencies, not correctness gates — pipeline passes `TickerLedger` correctness (`04-new-full-explanation-v2.md:128`) but wastes LLM $ / latency / I/O. List stays here as ledger; per-batch evidence goes in `implementations/batch-*.md`.

| # | Pipeline spot | What it is (simple) | Why inefficient / shortcoming | Evidence `file:line` | Status | Fix commit | Test |
|---|---|---|---|---|---|---|---|
| A | `1 Summary Agent` | `Summary Agent` writes same ticker summary **twice** per refresh (LLM team hook + `RunLogTrigger` own upsert) + `get_all_angles()` counted twice | Double DB write + duplicate `angles_tool` execution per cycle — last-write-wins, extra cost | `vinu-agent/agent/scheduler_workers.py:72-108` `make_summary_agent_fn` + `team.py:_apply_team_result_hook` + `vinu-agent/tools/angles_tool.py` | open | — | — |
| B | `1→2 Gate→Planner` | `planner-worker 1800s` checks tickers **one by one** sequentially, `PlannerTriage` + `HypothesisRegistry.query_by_symbol` per ticker | LLM-cost linear with 28 angles; no batch triage or parallel `TeamManager` workers (unlike `run_parameter_sweep_tool`) — K-cap still per-ticker `04-v2:65` | `vinu-agent/agent/planner_triage_hook.py`, `vinu-agent/config.py:65` | open | — | — |
| C | `2 Planner` idea | `idea_generator` recipe-first still calls `LlmStrategyGenerator` fallback on miss | One bad recipe still burns LLM without cheap gate like Thesis Intake `K-cap` `04-v2:29` | `vinu-research/generator.py:BUILTIN_RECIPES`, `vinu-research/llm_generator.py` | open | — | — |
| D | `3 Researcher` | `StrategyResearchLoop.run()` fetches `feature_snapshot` + 4 angle tables + `HypothesisRegistry` every run even when `from_date/to_date` unchanged | Repeated `features-api:8082` + `correlation:8083` `get_angle_rows` ×4 + `hypotheses.json.lock` 10s every call — no `research_from:research_to` cache like `story_cache` `loop.py:197` | `vinu-research/loop.py:197,236,244,283`, `vinu-research/tools.py:183` | open | — | — |
| E | `3 sweep` | `run_sweep_candidate` `sweep.py:135` `POST /simulator/simulate/custom` **per param** (loop) | `VectorBT` 1000 configs in seconds vs per-candidate round-trip; `N=5` re-runs same `substitute_param_value` AST walk `sweep.py:60` | `vinu-research/sweep.py:60,135`, `vinu-research/comparison.py`, `03-per-repo-deep-dive/vectorbt-sweep.md` | open | — | — |
| F | `5 Allocator` | `ComputeAllocationCandidatesTool` `POST /portfolio/evaluate-batch` per `900s` cycle `httpx 30s`, fail-closed `funding skipped` on unreachable | One `portfolio-api:8090` hiccup stalls entire `PEND` batch until next `900s` cycle — batch shrinks toward first-come | `vinu-agent/tools/allocation_tool.py:114-128` | open | — | — |
| G | `7 Monitor` plain poll | `cycle()` loops plans identically every cycle; `cycle_shock_batch(5)` built `d4c338ea` but **not auto-wired** to `shock_clustering` + `shock_personality` | Post A2-2, `Monitor` still pollutes `900s` poll without prioritization unless caller invokes `cycle_shock_batch`; `shock_personality` fetch `orchestrator.py:550` returns `None` until angle has `shock_score` field | `vinu-live/trade_plan/orchestrator.py:102,550`, `vinu-live/tests/test_trade_plan_orchestrator.py` | open | `d4c338ea` built, wiring open |
| H | Cross-cut `TickerLedger` | Every stage writes one row but never reads another stage's row except `SIG` detectors | No `ref_id` join validation in code — ledger can reference stale `BENCHING` after `PEND→ACTIVE` | `vinu-agent/storage/ticker_ledger.py:19`, `scheduler_workers.py:204` | open | — | — |
| I | Infra secrets | `docker-compose.yml:9` `env_file: .env` mounts secret values as plain env alongside `/run/secrets` `decisions/13` | `docker inspect`/`/proc` leaks if operator fills `.env`; `secrets_loader.py:44` fallback kept | `docker-compose.yml:9`, `decisions/13-env-gap-decision.md` | accepted | — | — |
| J | Data re-fetch | `service.py:152` `_build_returns_df` fetches `simulator/results/{id}/equity` **again** for `allocate_risk_parity` after `build_portfolio` already fetched | Double fetch same `equity` series per `900s` cycle; no cache like `freeze` `vinu_infra/freeze.py` | `vinu-portfolio/service.py:152,260` | open | — | — |

## How to use

- **Ledger here** = one table, no need to grep 10 commits — Status `open → spiked → built <sha>`.
- **Evidence** = `implementations/batch-*.md` per batch — `source file:line → dest file:line` + commit SHA + `pytest` line + how to verify.
- `test-plan/test-status/` is ephemeral run evidence (deletable per `run_id`); this file + `implementations/` is permanent architecture evidence (like `04-v2`).

## Next batches (cost first, per prior plan)

- **Batch Cost `B+D+E`** — planner batch + feature/angle cache + vectorized sweep — saves most LLM $ for next `2026-10-01` 28-angle harness.
- **Batch Latency `F+G`** — allocator retry window + auto `cycle_shock_batch` wiring.
- **Batch Ledger `H+J`** + **Infra `A+I`** — double-write dedupe + final `env_file` gap fix.

Update Status to `built <sha>` as each batch merges; delete `test-status` per `run_id` after gate green, keep this file forever.
