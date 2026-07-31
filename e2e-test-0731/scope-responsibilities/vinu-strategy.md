---
name: vinu-strategy
port: 8084
depends_on: [vinu-tools, vinu-initial-analysis]
---

# vinu-strategy

## What it does

Evaluates YAML-defined trading strategies (selection → allocation → timing
→ risk pipeline) into target portfolio weights.

## Scope for this E2E plan

Only 2 of the 3 Stage 1 tiers run here — the easy and medium tiers, both
written and in place:
- `vinu-components/vinu-strategy/strategies/e2e_easy_sma_crossover.yaml`
- `vinu-components/vinu-strategy/strategies/e2e_medium_trend_vol_filter.yaml`

Both are scoped to AAPL/TSLA/JNJ (`universe: {source: inline}`) and
evaluated against the 2022-01-01 → 2026-06-30 data.

**The complex tier does NOT run here.** `vinu-strategy`'s YAML DSL only
supports numeric/boolean comparisons (`gt`/`lt`/`eq`/etc.) on precomputed
features and correlation fields — there's no pipeline stage that calls an
LLM. "LLM forecast + probabilistic exit" runs through `vinu-research`'s
`POST /trade-plan/{symbol}` instead (see
[vinu-research.md](vinu-research.md)). This is a deliberate architectural
boundary, not a gap to close — keeping this service's execution layer
simple/deterministic/auditable and keeping LLM-driven forecasting in
`vinu-research` is the right split.

## When it runs

Depends on `vinu-tools` (features-api) and `vinu-initial-analysis`
(docker-compose `depends_on: features-api, initial-analysis-api`). Runs
after both are producing data, before `vinu-simulator` and `vinu-portfolio`.

## Where data is stored

- Evaluated weights: via `vinu_strategy/storage/weights.py`.
- Run metadata: via `vinu_strategy/storage/meta.py` (SQLite), under
  `VINU_STRATEGY_DATA_ROOT` (default `./data`).

## Dependencies

- `VINU_FEATURES_API_URL` (`vinu-tools`, port 8082)
- `VINU_CORRELATION_API_URL` (`vinu-initial-analysis`, port 8083)

## API surface used by this plan

- `GET /strategies` / `GET /strategies/{name}` — list/inspect configured
  strategies.
- `POST /strategies/{name}/evaluate` — the core call: produces target
  weights for a given date.
- `GET /weights` — retrieve evaluated weights history.

## Known gap as of this document

The medium tier's `volatility_20d gt 0.03` threshold is a single global
assumption across all 3 tickers — TSLA's baseline volatility is typically
higher than AAPL/JNJ's, so this may over-trigger on TSLA and under-trigger
on JNJ. Worth checking against real computed `volatility_20d` values once
`vinu-tools` has real data, and calibrating per-ticker later if it looks
wrong, not treated as correct by default.
