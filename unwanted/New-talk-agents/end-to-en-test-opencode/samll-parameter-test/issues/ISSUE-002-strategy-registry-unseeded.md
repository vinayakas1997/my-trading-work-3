# ISSUE-002 — Strategy registry loads empty: strategies dir bind mount never seeded

- **Component:** docker-compose.yml (`./data/strategy:/data/strategy`) / vinu-strategy `engine/registry.py` + `.env` `VINU_STRATEGY_STRATEGIES_DIR=/data/strategy/strategies`
- **Phase found:** 2 (Block 3)
- **Severity:** HIGH

## Description
The strategy YAML definitions ship in the image at `/app/vinu-strategy/strategies/`, but `.env` points the registry at `/data/strategy/strategies` (the bind mount), which was never seeded. `StrategyRegistry(...).load_all()` returns `[]`, so `POST /strategy/strategies/{name}/evaluate` fails with `Unknown strategy: e2e_easy_sma_crossover` while `GET /strategy/strategies` still lists them (that endpoint reads the DB registry table, populated earlier).

## Steps to reproduce
1. Fresh host with empty `./data/strategy/` and the compose `.env` values above.
2. `docker compose up -d quant-core-api`.
3. `POST /strategy/strategies/e2e_easy_sma_crossover/evaluate?symbols=AAPL`.

## Actual
`{"detail":"Unknown strategy: e2e_easy_sma_crossover","error":"validation_error"}` (0.03s) even though the strategy is listed by `GET /strategy/strategies`.

## Expected
Evaluate runs and returns weights.

## Impact
Quant-core's strategy evaluation (Block 3b and everything downstream) is broken on a fresh checkout; only cached DB metadata works.

## Suggested fix
Seed the strategies dir at container start (e.g. copy packaged YAMLs into `/data/strategy/strategies` if empty, in the image entrypoint) — or point `VINU_STRATEGY_STRATEGIES_DIR` back at the packaged path.

## Status
FIXED (workaround: `mkdir -p /data/strategy/strategies && cp /app/vinu-strategy/strategies/*.yaml /data/strategy/strategies/` as root, then `docker compose restart quant-core-api`). Root-cause fix (seeding in entrypoint/Dockerfile) still recommended.

## Evidence
- `evidence/03-analysis/strategy-evaluate-aapl.json` (post-fix 200 with weight)
- Container: `/app/vinu-strategy/strategies/*.yaml` (6 files) vs `/data/strategy/strategies` (was empty)
