---
name: vinu-research
port: 8087
depends_on: [vinu-tools, vinu-simulator, vinu-initial-analysis, vinu-stock-price]
---

# vinu-research

## What it does

Automated strategy research/refinement loop — generates and iteratively
improves strategies (template-driven or LLM-assisted), runs
walk-forward/holdout/stress tests, and promotes strategies from BENCHING to
ACTIVE with ongoing decay monitoring.

## Scope for this E2E plan

**This is where the complex tier actually runs — the whole tier, not just
generation.** Unlike the easy/medium tiers (hand-written `vinu-strategy`
YAMLs, evaluated via `vinu-strategy`'s `evaluate()`), the complex tier has
no YAML and is never evaluated by `vinu-strategy` at all — it is tested
directly against this service's `POST /trade-plan/{symbol}` for
AAPL/TSLA/JNJ, which internally calls the LLM
(`forecast_skill.py`) and applies calibrated probabilistic-exit logic
(`trade_plan_authoring.py`, `judgment_store.py` — built in Step 03 of the
prior audit plan). Testing this tier means inspecting that endpoint's real
output, not writing rule conditions.

Also the service that records each Stage 1 run as a queryable artifact,
which is what the plan's "research again" step between Stage 1 and
Stage 2 will pull from.

## When it runs

Depends on `vinu-tools`, `vinu-simulator`, `vinu-initial-analysis`,
`vinu-stock-price` (docker-compose `depends_on: features-api,
simulator-api, initial-analysis-api, stock-api`) — it's downstream of
almost everything, since generating and testing a strategy candidate needs
features, price data, correlation context, and a way to backtest the
candidate.

## Where data is stored

SQLite backend (`storage/sqlite_backend.py`) and
`storage/strategy_store.py` for artifacts/hypotheses, under
`VINU_RESEARCH_DATA_ROOT` (default `./data`).

## Dependencies

- `VINU_FEATURES_API_URL` (port 8082)
- `VINU_SIMULATOR_API_URL` (port 8085)
- `VINU_CORRELATION_API_URL` (port 8083)
- `VINU_STOCK_PRICE_API_URL` (port 8081)
- Local LLM via `VINU_LLM_BASE_URL=http://host.docker.internal:8009/v1`
  (model `qwen36-35B`) when `llm_enabled` / `generator_mode=hybrid` —
  **required** for the complex-tier strategy specifically; without it this
  tier cannot run as designed.

## API surface used by this plan

- `POST /run` / `POST /ensure` — generate/refine a strategy candidate.
- `POST /artifacts/{id}/promote` — BENCHING → ACTIVE promotion.
- `POST /trade-plan/{symbol}` and `/trade-plan/{artifact_id}/calibration` —
  the probabilistic-exit calibration data path (built in Step 03 of the
  prior audit plan).

## Known gaps as of this document

- `VINU_RESEARCH_LLM_ENABLED` is currently `false` in
  `vinu-components/.env` — needs to be flipped to `true` before this
  service will actually call the LLM for the complex tier. Without it,
  the endpoint likely falls back to template-driven generation, which
  would defeat the point of having a "complex" tier distinct from the
  medium one.
- Whether `http://host.docker.internal:8009/v1` is actually reachable from
  inside the `research-api` container has not been verified yet — real
  first test item, not an assumption to skip.
